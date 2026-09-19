"""Config tests: validators, 0600 storage, resolution precedence (flag > env > ephemeral > default)."""

import os
import stat

import pydantic
import pytest

from mycli import config


def test_profile_rejects_non_http_url():
    with pytest.raises(pydantic.ValidationError):
        config.Profile(name="x", url="ftp://host")


def test_profile_rejects_unsafe_name():
    with pytest.raises(pydantic.ValidationError):
        config.Profile(name="../evil", url="https://h")


def test_save_load_roundtrip_and_mode(make_profile, isolated_config):
    make_profile("prod", token="t0k", timeout=5)
    path = isolated_config / "profiles" / "prod.json"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    loaded = config.load_profile("prod")
    assert loaded.token == "t0k" and loaded.timeout == 5.0 and loaded.retries == 3


def test_load_missing_returns_none():
    assert config.load_profile("ghost") is None


def test_default_profile_roundtrip(isolated_config):
    assert config.default_profile_name() == ""
    config.set_default_profile("prod")
    assert config.default_profile_name() == "prod"
    (isolated_config / "config.toml").write_text("=[broken")
    assert config.default_profile_name() == ""


def test_list_profiles_sorted(make_profile):
    make_profile("b")
    make_profile("a")
    assert [p.name for p in config.list_profiles()] == ["a", "b"]


def test_resolve_flag_wins_over_env_and_default(monkeypatch, make_profile):
    make_profile("flagged", token="flag-tok")
    make_profile("defaulted")
    config.set_default_profile("defaulted")
    monkeypatch.setenv("MYCLI_PROFILE", "flagged")
    assert config.resolve_profile("flagged").token == "flag-tok"


def test_resolve_env_profile_beats_default(monkeypatch, make_profile):
    make_profile("envpicked", token="env-tok")
    make_profile("defaulted")
    config.set_default_profile("defaulted")
    monkeypatch.setenv("MYCLI_PROFILE", "envpicked")
    assert config.resolve_profile().token == "env-tok"


def test_resolve_ephemeral_env_url(monkeypatch):
    monkeypatch.setenv("MYCLI_URL", "https://adhoc.example")
    monkeypatch.setenv("MYCLI_TOKEN", "adhoc-tok")
    resolved = config.resolve_profile()
    assert resolved.url == "https://adhoc.example" and resolved.token == "adhoc-tok"


def test_resolve_stored_default(monkeypatch, make_profile):
    make_profile("defaulted", token="def-tok")
    config.set_default_profile("defaulted")
    assert config.resolve_profile().token == "def-tok"


def test_resolve_none_when_unconfigured():
    assert config.resolve_profile() is None
