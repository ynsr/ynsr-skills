"""End-to-end via the real entry point (main()): envelope shape, exit codes, purity, non-block.

Runs .venv/bin/mycli as a subprocess (CliRunner bypasses main(), where the envelope lives).
Requires a synced venv (uv sync); skipped otherwise. All offline.
"""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

BIN = Path(sys.executable).parent / "mycli"  # .venv/bin/mycli when running under uv run pytest
pytestmark = pytest.mark.skipif(not BIN.is_file(), reason=".venv/bin/mycli missing (run: uv sync)")


def run(*args, tmp_path=None, env_extra=None, timeout=10):
    env = dict(os.environ)
    if tmp_path is not None:
        env["MYCLI_CONFIG_DIR"] = str(tmp_path / "cfg")
    for var in ("MYCLI_TOKEN", "MYCLI_PROFILE", "MYCLI_OUTPUT", "MYCLI_URL",
                "MYCLI_VERBOSE", "MYCLI_QUIET", "MYCLI_NO_INPUT", "NO_COLOR", "CI"):
        env.pop(var, None)
    env.update(env_extra or {})
    return subprocess.run([str(BIN), *args], capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=timeout, env=env)


def test_bad_subcommand_envelope_and_exit(tmp_path):
    proc = run("__nope__", tmp_path=tmp_path)
    assert proc.returncode == 2
    assert proc.stdout == ""  # errors never touch stdout
    env = json.loads(proc.stderr)  # non-TTY stderr → agent envelope
    assert env["error"]["code"] == "usage"
    assert env["error"]["message"] and env["error"]["hint"]


def test_envelope_via_json_output_flag(tmp_path):
    proc = run("list", "widgets", "-o", "json", "__nope__", tmp_path=tmp_path)
    assert proc.returncode == 2
    assert json.loads(proc.stderr)["error"]["code"] == "usage"


def test_help_documents_exit_codes_and_version(tmp_path):
    help_out = run("--help", tmp_path=tmp_path)
    assert help_out.returncode == 0 and "exit code" in help_out.stdout.lower()
    version = run("--version", tmp_path=tmp_path)
    assert version.returncode == 0 and version.stdout.startswith("mycli ")

def test_bare_invocation_is_usage_error(tmp_path):
    proc = run(tmp_path=tmp_path)
    assert proc.returncode == 2  # no command given: usage error, never a hang
    assert json.loads(proc.stderr)["error"]["code"] == "usage"

def test_stdout_purity(tmp_path):
    proc = run("list", "widgets", tmp_path=tmp_path)
    assert proc.returncode == 0 and proc.stdout
    assert not any(c in proc.stdout for c in "╭╰│├└") and "\x1b" not in proc.stdout


def test_no_ansi_env_and_flag(tmp_path):
    env_out = run("list", "widgets", "-o", "table", tmp_path=tmp_path,
                  env_extra={"NO_COLOR": "1", "TERM": "dumb"}).stdout
    assert "\x1b" not in env_out
    flag_out = run("list", "widgets", "-o", "table", "--no-color", tmp_path=tmp_path).stdout
    assert "\x1b" not in flag_out  # no env vars set for this leg


def test_output_matrix_subprocess(tmp_path):
    data = run("list", "widgets", "--output", "json", tmp_path=tmp_path)
    assert data.returncode == 0 and json.loads(data.stdout)[0]["name"] == "alpha"
    for fmt, delim in (("csv", ","), ("tsv", "\t")):
        proc = run("list", "widgets", "-o", fmt, tmp_path=tmp_path)
        assert proc.returncode == 0
        assert delim in proc.stdout.splitlines()[0]


def test_non_tty_never_blocks_or_prompts(tmp_path):
    # no name arg, no --dry-run/--yes: must fail fast with the envelope, never wait for stdin
    proc = run("profile", "remove", tmp_path=tmp_path)
    assert proc.returncode == 2
    assert json.loads(proc.stderr)["error"]["code"] == "usage"
    assert proc.stdout == ""


def test_dry_run_plan_on_stdout(tmp_path):
    proc = run("profile", "remove", "demo", "--dry-run", tmp_path=tmp_path)
    assert proc.returncode == 0
    assert "would remove profile 'demo'" in proc.stdout
    assert not (tmp_path / "cfg").exists() or not any((tmp_path / "cfg" / "profiles").glob("demo*"))


def test_completion_bash_via_real_entry(tmp_path):
    proc = run("completion", "bash", tmp_path=tmp_path)
    assert proc.returncode == 0 and "_mycli_completion" in proc.stdout


def test_profile_create_roundtrip_subprocess(tmp_path):
    proc = run("profile", "create", "prod", "--url", "https://prod.example", "--default",
               tmp_path=tmp_path, env_extra={"MYCLI_TOKEN": "s3cret"})
    assert proc.returncode == 0
    saved = tmp_path / "cfg" / "profiles" / "prod.json"
    assert saved.is_file()
    assert stat.S_IMODE(saved.stat().st_mode) == 0o600
    listed = run("profile", "list", "-o", "json", tmp_path=tmp_path)
    assert "s3cret" not in listed.stdout  # secrets never on stdout
    assert json.loads(listed.stdout)[0]["default"] is True
