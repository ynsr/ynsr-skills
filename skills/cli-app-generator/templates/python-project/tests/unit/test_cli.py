"""Surface tests (fast, in-process): output matrix, profile ops, doctor, completion, schema."""

import inspect
import json

import pytest
from typer.testing import CliRunner

from mycli.cli import app

if "mix_stderr" in inspect.signature(CliRunner.__init__).parameters:
    runner = CliRunner(mix_stderr=False)  # click 8.1: keep streams separate
else:
    runner = CliRunner()  # click >=8.2: separate by default


def invoke(*args):
    return runner.invoke(app, list(args))


def envelope(result) -> dict:
    """In-process errors surface as the raised exception (CliRunner bypasses main())."""
    from mycli.output import CliError

    assert isinstance(result.exception, CliError), result.exception
    return {"error": {"code": result.exception.code, "hint": result.exception.hint}}


def test_version():
    result = invoke("--version")
    assert result.exit_code == 0
    assert result.output.startswith("mycli ")


def test_help_documents_exit_codes():
    result = invoke("--help")
    assert result.exit_code == 0
    assert "exit code" in result.output.lower()


def test_default_output_is_csv():
    result = invoke("list", "widgets")
    assert result.exit_code == 0
    assert result.output.splitlines()[0] == "id,name,size,created"


def test_output_json():
    result = invoke("list", "widgets", "--output", "json")
    assert result.exit_code == 0
    assert (rows := json.loads(result.output))
    assert rows[0]["name"] == "alpha"


def test_output_csv_and_tsv():
    csv_result = invoke("list", "widgets", "-o", "csv")
    assert csv_result.exit_code == 0
    assert csv_result.output.splitlines()[0] == "id,name,size,created"
    tsv_result = invoke("list", "widgets", "-o", "tsv")
    assert tsv_result.exit_code == 0
    assert "\t" in tsv_result.output and tsv_result.output.splitlines()[0] == "id\tname\tsize\tcreated"


def test_json_alias():
    result = invoke("list", "widgets", "--json")
    assert result.exit_code == 0
    assert json.loads(result.output)[0]["id"] == 1


def test_output_precedence_flag_beats_alias():
    result = invoke("list", "widgets", "-o", "csv", "--json")
    assert result.exit_code == 0
    assert result.output.splitlines()[0] == "id,name,size,created"  # --output wins over --json


def test_table_no_box_or_ansi():
    result = invoke("list", "widgets", "-o", "table")
    assert result.exit_code == 0
    assert "ID" in result.output
    assert not any(c in result.output for c in "╭╰│├└") and "\x1b" not in result.output


def test_fields_and_limit():
    result = invoke("list", "widgets", "--fields", "id,name", "--limit", "2")
    assert result.exit_code == 0
    lines = result.output.splitlines()
    assert lines[0] == "id,name" and len(lines) == 3


def test_unknown_subcommand_is_usage_error():
    # envelope shape + exit 2 via real main() proven by test_surface_subprocess
    result = invoke("__nope__")
    assert result.exit_code == 2
    assert result.stdout == ""


def test_profile_create_env_token(isolated_config, monkeypatch):
    monkeypatch.setenv("MYCLI_TOKEN", "s3cret")
    result = invoke("profile", "create", "prod", "--url", "https://prod.example")
    assert result.exit_code == 0
    saved = isolated_config / "profiles" / "prod.json"
    assert saved.is_file()
    assert "s3cret" in saved.read_text()
    import os
    import stat

    assert stat.S_IMODE(os.stat(saved).st_mode) == 0o600

    toml = isolated_config / "config.toml"
    assert not toml.exists() or "default_profile" not in toml.read_text()
def test_profile_create_default(isolated_config):
    result = invoke("profile", "create", "prod", "--url", "https://prod.example", "--default")
    assert result.exit_code == 0
    import tomllib

    data = tomllib.loads((isolated_config / "config.toml").read_text())
    assert data["default_profile"] == "prod"


def test_profile_create_bad_url():
    result = invoke("profile", "create", "bad", "--url", "ftp://x")
    assert envelope(result)["error"]["code"] == "usage"
    assert not result.stdout


def test_profile_list_hides_token(make_profile):
    make_profile("a", token="hidden-token")
    make_profile("b")
    result = invoke("profile", "list", "-o", "json")
    assert result.exit_code == 0
    assert "hidden-token" not in result.output
    rows = json.loads(result.output)
    assert [r["name"] for r in rows] == ["a", "b"]
    assert next(r for r in rows if r["name"] == "a")["default"] is False


def test_profile_remove_dry_run_missing():
    result = invoke("profile", "remove", "demo", "--dry-run")
    assert result.exit_code == 0
    assert "would remove profile 'demo'" in result.stdout
    assert "not present" in result.stdout


def test_profile_remove_dry_run_existing(make_profile, isolated_config):
    make_profile("gone")
    result = invoke("profile", "remove", "gone", "--dry-run")
    assert result.exit_code == 0
    assert "would remove" in result.stdout
    assert (isolated_config / "profiles" / "gone.json").is_file()  # changed nothing


def test_profile_remove_refuses_without_yes(make_profile):
    make_profile("gone")
    result = invoke("profile", "remove", "gone")
    assert "--yes" in envelope(result)["error"]["hint"]
    assert result.stdout == ""


def test_profile_remove_yes(make_profile, isolated_config):
    make_profile("gone")
    result = invoke("profile", "remove", "gone", "--yes")
    assert result.exit_code == 0
    assert not (isolated_config / "profiles" / "gone.json").exists()


def test_profile_remove_yes_missing():
    result = invoke("profile", "remove", "ghost", "--yes")
    assert envelope(result)["error"]["code"] == "error"


def test_doctor_ok():
    result = invoke("doctor")
    assert result.exit_code == 0
    assert result.output.splitlines()[0] == "status: ok"


def test_doctor_json_single_line():
    result = invoke("doctor", "--json")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "ok"


def test_doctor_flags_broken_config(isolated_config):
    (isolated_config / "config.toml").write_text("not [ valid toml")
    result = invoke("doctor")
    assert result.exit_code == 1
    assert result.output.splitlines()[0] == "status: missing"


def test_completion_bash_script():
    result = invoke("completion", "bash")
    assert result.exit_code == 0
    assert "_mycli_completion" in result.output


def test_completion_invalid_shell():
    result = invoke("completion", "tcsh")  # envelope via real main() proven by subprocess tests
    assert result.exit_code == 2


@pytest.mark.parametrize("shell", ["zsh", "fish"])
def test_completion_zsh_fish(shell):
    result = invoke("completion", shell)
    assert result.exit_code == 0 and result.output


def test_schema_json():
    result = invoke("schema")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "list" in data["commands"] and "profile" in data["commands"]
    assert data["profile_schema"]["properties"]["token"]["type"] == "string"
