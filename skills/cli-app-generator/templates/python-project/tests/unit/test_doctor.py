"""Doctor tests: install receipt vs live-tree sync (offline; HOME redirected)."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from mycli import doctor
from mycli.cli import app

if "mix_stderr" in __import__("inspect").signature(CliRunner.__init__).parameters:
    runner = CliRunner(mix_stderr=False)
else:
    runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_share(tmp_path, monkeypatch):
    """Redirect the receipt store ($HOME) per test."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return tmp_path / "home"


@pytest.fixture()
def fake_repo(tmp_path):
    """A fake source checkout: repo/src/mycli with two modules."""
    pkg = tmp_path / "repo" / "src" / "mycli"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("__version__ = '0.1.0'\n")
    (pkg / "ops.py").write_text("x = 1\n")
    return tmp_path / "repo"


def write_receipt(source_dir, source_hash):
    receipt = doctor.share_dir() / "install-receipt.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(
        {"source_hash": source_hash, "installed_at": "2026-01-01T00:00:00+00:00",
         "source_dir": str(source_dir)}))


def test_source_hash_sensitive_and_stable(fake_repo):
    """Same content → same hash; one changed file → different hash."""
    pkg = fake_repo / "src" / "mycli"
    first = doctor.source_hash(pkg)
    assert first == doctor.source_hash(pkg)
    (pkg / "client.py").write_text("y = 2\n")
    assert doctor.source_hash(pkg) != first


def test_check_ok(fake_repo):
    write_receipt(fake_repo, doctor.source_hash(fake_repo / "src" / "mycli"))
    status, message = doctor.check()
    assert status == doctor.OK
    assert "in sync" in message


def test_check_stale_after_edit(fake_repo):
    """Receipt taken before an edit reports stale with the fix command."""
    write_receipt(fake_repo, doctor.source_hash(fake_repo / "src" / "mycli"))
    (fake_repo / "src" / "mycli" / "ops.py").write_text("x = 2\n")
    status, message = doctor.check()
    assert status == doctor.STALE
    assert "./install.sh" in message


def test_check_missing_receipt():
    status, message = doctor.check()
    assert status == doctor.MISSING
    assert "./install.sh" in message


def test_check_missing_source_dir(fake_repo):
    """Receipt whose recorded checkout is gone reports missing."""
    write_receipt(fake_repo / "gone", "abc")
    status, message = doctor.check()
    assert status == doctor.MISSING
    assert "./install.sh" in message


def test_cli_doctor_ok(fake_repo):
    write_receipt(fake_repo, doctor.source_hash(fake_repo / "src" / "mycli"))
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "in sync" in result.output


def test_cli_doctor_stale_exits_1(fake_repo):
    """mycli doctor exits 1 and names the fix when stale."""
    write_receipt(fake_repo, doctor.source_hash(fake_repo / "src" / "mycli"))
    (fake_repo / "src" / "mycli" / "ops.py").write_text("x = 3\n")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "source changed since install" in result.output


def test_dev_warning_silent_without_receipt():
    assert doctor.dev_warning() is None


def test_dev_warning_fires_on_mismatch(fake_repo):
    """Running from the tree with a mismatched receipt warns to reinstall."""
    write_receipt(fake_repo, "deadbeef0000")
    warning = doctor.dev_warning()
    assert warning is not None
    assert "./install.sh" in warning


def test_dev_warning_never_from_installed_copy(fake_repo, tmp_path):
    """A path under site-packages never warns, even with a bad receipt."""
    write_receipt(fake_repo, "deadbeef0000")
    installed = tmp_path / "site-packages" / "mycli" / "doctor.py"
    assert doctor.dev_warning(here=installed) is None
