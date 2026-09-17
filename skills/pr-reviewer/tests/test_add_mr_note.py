"""Tests for scripts/add_mr_note.py (command construction only; never posts)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from add_mr_note import build_command, post_note  # noqa: E402

PROJ = "https://git.jibit.cloud/server/ipg-commons"


def test_general_comment():
    assert build_command(PROJ, "38", "LGTM") == \
        ["glab", "mr", "note", "create", "-R", PROJ, "38", "-m", "LGTM"]


def test_inline_new_side_line():
    cmd = build_command(PROJ, "38", "Needs refactoring", file="a/Main.java", line="42")
    assert "--file" in cmd and "a/Main.java" in cmd
    assert "--line" in cmd and "42" in cmd


def test_inline_range_and_old_line():
    cmd = build_command(PROJ, "38", "Extract", file="a.java", line="10:15")
    assert "10:15" in cmd
    cmd = build_command(PROJ, "38", "Why removed?", file="a.java", old_line=7)
    assert "--old-line" in cmd and "7" in cmd


def test_unique_and_reply_and_non_resolvable():
    assert "--unique" in build_command(PROJ, "38", "x", unique=True)
    assert "--reply" in build_command(PROJ, "38", "x", reply="abc12345")
    assert "--resolvable=false" in build_command(PROJ, "38", "status", resolvable=False)


def test_rejected_combinations():
    with pytest.raises(ValueError, match="cannot be used together"):
        build_command(PROJ, "38", "x", file="a", line="1", old_line=2)
    with pytest.raises(ValueError, match="require --file"):
        build_command(PROJ, "38", "x", line="1")
    with pytest.raises(ValueError, match="mutually exclusive"):
        build_command(PROJ, "38", "x", file="a", reply="abc12345")
    with pytest.raises(ValueError, match="mutually exclusive"):
        build_command(PROJ, "38", "x", unique=True, file="a")
    with pytest.raises(ValueError, match="--resolvable=false"):
        build_command(PROJ, "38", "x", file="a", resolvable=False)


def test_post_note_pipes_stdin_body(monkeypatch):
    """Long markdown bodies go via stdin, not -m (quoting safety)."""
    seen = {}

    class FakeResult:
        stdout = "created\n"

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["input"] = kwargs.get("input")
        assert kwargs.get("check") is True
        return FakeResult()

    monkeypatch.setattr("add_mr_note.subprocess.run", fake_run)
    out = post_note(["glab", "mr", "note", "create"], body_from_stdin="**md** `code` $v")
    assert out == "created"
    assert seen["input"] == "**md** `code` $v"


def test_post_note_wraps_cli_errors(monkeypatch):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        raise sp.CalledProcessError(1, cmd, stderr="401 Unauthorized")

    monkeypatch.setattr("add_mr_note.subprocess.run", fake_run)
    with pytest.raises(RuntimeError, match="401 Unauthorized"):
        post_note(["glab"])
