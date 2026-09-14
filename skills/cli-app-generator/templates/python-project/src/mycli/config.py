"""Profile storage and resolution.

Profiles are JSON files under ~/.config/mycli/profiles/ (mode 0600; override
dir with MYCLI_CONFIG_DIR — used by tests). Resolution order:

1. --profile NAME flag (or MYCLI_PROFILE env var feeding it)
2. MYCLI_URL env var (+ MYCLI_TOKEN / MYCLI_USER + MYCLI_PASS) — ephemeral
3. the profile recorded as default in config.json

Secrets live only in local profile files (0600); never logged.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field, fields as dc_fields
from pathlib import Path
from typing import Any

__all__ = ["Profile", "ProfileError", "config_dir", "save_profile", "load_profile",
           "list_profiles", "delete_profile", "get_default", "set_default", "resolve_profile"]


class ProfileError(Exception):
    """Missing or invalid profile configuration."""


@dataclass
class Profile:
    """Connection settings for one source. Adjust fields to your domain."""

    name: str
    url: str
    token: str | None = None            # secret — 0600 file only
    verify_tls: bool = True
    timeout: float = 30.0
    retries: int = 3
    retry_delay: float = 1.0
    default_resource: str | None = None  # e.g. default collection/table/project
    extra_headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.url:
            raise ProfileError("profile url is required")
        if not self.url.startswith(("http://", "https://")):
            raise ProfileError(f"url must start with http:// or https:// (got {self.url!r})")

    def redacted(self) -> dict[str, Any]:
        d = asdict(self)
        if d.get("token"):
            d["token"] = "***set***"
        return d

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def config_dir() -> Path:
    root = os.environ.get("MYCLI_CONFIG_DIR")
    return Path(root).expanduser() if root else Path.home() / ".config" / "mycli"


def _profile_path(name: str) -> Path:
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        raise ProfileError(f"invalid profile name: {name!r}")
    return config_dir() / "profiles" / f"{name}.json"


def save_profile(p: Profile) -> None:
    path = _profile_path(p.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(p.to_dict(), fh, indent=2, sort_keys=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)  # atomic
    except OSError:
        os.unlink(tmp)
        raise


def load_profile(name: str) -> Profile:
    path = _profile_path(name)
    if not path.exists():
        available = ", ".join(sorted(p.stem for p in list_profiles_dir())) or "none"
        raise ProfileError(f"profile '{name}' not found at {path} (available: {available})")
    data = json.loads(path.read_text(encoding="utf-8"))
    known = {f.name for f in dc_fields(Profile)}
    filtered = {k: v for k, v in data.items() if k in known and k != "name"}
    try:
        return Profile(name=name, **filtered)
    except TypeError as exc:
        raise ProfileError(f"invalid profile data in {path}: {exc}") from exc


def list_profiles_dir() -> list[Path]:
    d = config_dir() / "profiles"
    return sorted(d.glob("*.json")) if d.is_dir() else []


def list_profiles() -> dict[str, Profile]:
    return {p.stem: load_profile(p.stem) for p in list_profiles_dir()}


def delete_profile(name: str) -> None:
    path = _profile_path(name)
    if path.exists():
        path.unlink()


def _config_json() -> dict[str, Any]:
    path = config_dir() / "config.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return {}


def get_default() -> str | None:
    return _config_json().get("default_profile")


def set_default(name: str) -> None:
    config_dir().mkdir(parents=True, exist_ok=True)
    path = config_dir() / "config.json"
    data = _config_json()
    data["default_profile"] = name
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolve_profile(flag_value: str | None) -> Profile:
    """--profile NAME > MYCLI_PROFILE > ephemeral env > stored default."""
    name = flag_value or os.environ.get("MYCLI_PROFILE")
    if name:
        return load_profile(name)
    url = os.environ.get("MYCLI_URL")
    if url:  # ephemeral unnamed profile from env
        return Profile(
            name="env",
            url=url,
            token=os.environ.get("MYCLI_TOKEN"),
            verify_tls=os.environ.get("MYCLI_VERIFY_TLS", "1") not in ("0", "false"),
        )
    default = get_default()
    if default:
        return load_profile(default)
    raise ProfileError(
        "no profile available. Either pass --profile NAME, set MYCLI_URL (+ MYCLI_TOKEN), "
        "set MYCLI_PROFILE, or mark one as default: mycli profile use NAME"
    )
