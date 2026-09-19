"""Shared fixtures: isolated config dir (ambient env purged), no network."""

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mycli import config as cfg


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Every test gets its own config dir; ambient env must not leak in."""
    monkeypatch.setenv("MYCLI_CONFIG_DIR", str(tmp_path / "cfg"))
    for var in ("MYCLI_URL", "MYCLI_TOKEN", "MYCLI_PROFILE", "MYCLI_OUTPUT", "MYCLI_LIMIT",
                "MYCLI_VERBOSE", "MYCLI_QUIET", "MYCLI_NO_INPUT", "NO_COLOR", "CI",
                "ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy",
                "HTTPS_PROXY", "https_proxy", "NO_PROXY", "no_proxy"):
        monkeypatch.delenv(var, raising=False)
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    return tmp_path / "cfg"


@pytest.fixture
def make_profile():
    def _make(name="test", **overrides):
        p = cfg.Profile(name=name, url=overrides.pop("url", "https://api.test"), **overrides)
        cfg.save_profile(p)
        return p

    return _make
