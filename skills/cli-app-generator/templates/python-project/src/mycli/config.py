"""Profile store: 0600 JSON files + config.toml default; env-var precedence (resolve_profile)."""

import os
import re
import tomllib
from pathlib import Path

import pydantic
from platformdirs import user_config_dir


class Profile(pydantic.BaseModel):
    """Connection profile: url + token (secret) + client knobs."""

    name: str
    url: str
    token: str = ""
    timeout: float = 30.0
    retries: int = 3
    retry_delay: float = 1.0
    verify_tls: bool = True

    @pydantic.field_validator("name")
    @classmethod
    def _safe_name(cls, v: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", v):
            raise ValueError("use letters, digits, - or _")
        return v

    @pydantic.field_validator("url")
    @classmethod
    def _http_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return v


def config_dir() -> Path:
    """Root config dir; override with MYCLI_CONFIG_DIR (tests/sandboxes)."""
    return Path(os.environ.get("MYCLI_CONFIG_DIR") or user_config_dir("mycli"))


def profile_path(name: str) -> Path:
    return config_dir() / "profiles" / f"{name}.json"


def load_profile(name: str) -> Profile | None:
    path = profile_path(name)
    return Profile.model_validate_json(path.read_text()) if path.is_file() else None


def save_profile(profile: Profile) -> Path:
    directory = config_dir() / "profiles"
    directory.mkdir(parents=True, exist_ok=True)
    path = profile_path(profile.name)
    path.write_text(profile.model_dump_json())
    path.chmod(0o600)  # token at rest
    return path


def default_profile_name() -> str:
    try:
        return str(tomllib.loads((config_dir() / "config.toml").read_text()).get("default_profile", ""))
    except (FileNotFoundError, tomllib.TOMLDecodeError):
        return ""


def set_default_profile(name: str) -> None:
    toml = config_dir() / "config.toml"
    toml.parent.mkdir(parents=True, exist_ok=True)
    toml.write_text(f'default_profile = "{name}"\n')


def list_profiles() -> list[Profile]:
    directory = config_dir() / "profiles"
    return [load_profile(p.stem) for p in sorted(directory.glob("*.json"))] if directory.is_dir() else []


def resolve_profile(flag: str | None = None) -> Profile | None:
    """flag > MYCLI_PROFILE > ephemeral MYCLI_URL/MYCLI_TOKEN > stored default (None = unconfigured)."""
    name = flag or os.environ.get("MYCLI_PROFILE") or ""
    if name:
        return load_profile(name)
    if os.environ.get("MYCLI_URL"):
        return Profile(name="env", url=os.environ["MYCLI_URL"], token=os.environ.get("MYCLI_TOKEN", ""))
    name = default_profile_name()
    return load_profile(name) if name else None
