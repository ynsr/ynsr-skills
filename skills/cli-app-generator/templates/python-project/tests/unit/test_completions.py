"""Completion tests: show output, idempotent install, value completion."""

import click
import typer.main
from typer.testing import CliRunner

from mycli import cli as cli_mod
from mycli import completions as comp
from mycli.cli import app

if "mix_stderr" in __import__("inspect").signature(CliRunner.__init__).parameters:
    runner = CliRunner(mix_stderr=False)
else:
    runner = CliRunner()


def test_show_bash_prints_evalable_script():
    result = runner.invoke(app, ["completions", "show", "bash"])
    assert result.exit_code == 0
    assert "_mycli_completion" in result.output
    assert "COMP_WORDS" in result.output


def test_show_rejects_unknown_shell():
    result = runner.invoke(app, ["completions", "show", "tcsh"])
    assert result.exit_code == 2


def test_install_idempotent(tmp_path, monkeypatch):
    rc = tmp_path / ".bashrc"
    rc.write_text("# existing\nexport FOO=1\n")
    monkeypatch.setenv("SHELL", "/bin/bash")
    first = runner.invoke(app, ["completions", "install", "bash", "--rcfile", str(rc), "--yes"])
    assert first.exit_code == 0
    body = rc.read_text()
    assert 'eval "$(mycli completions show bash)"' in body
    assert "export FOO=1" in body  # existing content preserved
    assert (tmp_path / ".bashrc.bak").is_file()
    second = runner.invoke(app, ["completions", "install", "bash", "--rcfile", str(rc), "--yes"])
    assert second.exit_code == 0
    assert rc.read_text() == body  # no-op on re-run
    assert body.count(">>> mycli completions >>>") == 1


def test_install_detects_shell_from_env(tmp_path, monkeypatch):
    rc = tmp_path / ".zshrc"
    monkeypatch.setenv("SHELL", "/bin/zsh")
    result = runner.invoke(app, ["completions", "install", "--rcfile", str(rc), "--yes"])
    assert result.exit_code == 0
    assert "compinit" in rc.read_text()  # zsh needs compinit before eval


def test_subcommands_and_flags_come_from_click():
    cmd = typer.main.get_command(app)
    ctx = click.Context(cmd, info_name="mycli")
    assert {"init", "list", "profile", "completions"} <= {i.value for i in cmd.shell_complete(ctx, "")}
    list_cmd = cmd.get_command(ctx, "list")
    ctx2 = click.Context(list_cmd, info_name="list", parent=ctx)
    assert "--profile" in {i.value for i in list_cmd.shell_complete(ctx2, "--")}


def test_profile_value_completion_lists_local_profiles(make_profile):
    make_profile("prod")
    make_profile("dev")
    assert cli_mod._complete_profiles(None, "") == ["dev", "prod"]
    assert cli_mod._complete_profiles(None, "pr") == ["prod"]


def test_value_completion_never_raises(isolated_config):
    # empty/missing profile dir must yield [], not break Tab
    assert cli_mod._complete_profiles(None, "") == []


def test_detect_shell_rejects_unknown(monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/tcsh")
    assert comp.detect_shell() is None
