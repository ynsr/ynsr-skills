"""emit()/fail() unit tests: format matrix, field subsets, envelope shape."""

import json

import pytest

from mycli import output
from mycli.output import emit, fail

ROWS = [{"id": 1, "name": "a", "size": 10}, {"id": 2, "name": "b", "size": 20}]


def test_emit_csv(capsys):
    emit(ROWS, "csv")
    assert capsys.readouterr().out == "id,name,size\n1,a,10\n2,b,20\n"


def test_emit_tsv(capsys):
    emit(ROWS, "tsv")
    assert capsys.readouterr().out == "id\tname\tsize\n1\ta\t10\n2\tb\t20\n"


def test_emit_fields_subset(capsys):
    emit(ROWS, "csv", ["size", "id"])
    assert capsys.readouterr().out == "size,id\n10,1\n20,2\n"


def test_emit_fields_missing_key_blank(capsys):
    emit(ROWS, "csv", ["id", "ghost"])
    assert capsys.readouterr().out == "id,ghost\n1,\n2,\n"


def test_emit_json_types_preserved(capsys):
    emit(ROWS, "json")
    assert json.loads(capsys.readouterr().out) == ROWS  # ints stay ints


def test_emit_json_empty(capsys):
    emit([], "json")
    assert capsys.readouterr().out == "[]\n"


def test_emit_csv_empty_nothing(capsys):
    emit([], "csv")
    assert capsys.readouterr().out == ""


def test_emit_table_alignment_and_no_boxes(capsys):
    emit(ROWS, "table")
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "ID  NAME  SIZE"
    assert out.splitlines()[1].rstrip() == "1   a     10"


def test_emit_agent_default_is_csv(capsys):
    emit(ROWS, None)
    assert capsys.readouterr().out.startswith("id,name,size")


def test_emit_human_default_is_table(monkeypatch, capsys):
    monkeypatch.setattr(output, "AUDIENCE", "human")
    emit(ROWS, None)
    assert capsys.readouterr().out.splitlines()[0] == "ID  NAME  SIZE"


def test_fail_envelope_on_non_tty(capsys):
    with pytest.raises(SystemExit) as exc:
        fail("boom", "usage", "try --help", 2)
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert json.loads(captured.err) == {"error": {"code": "usage", "message": "boom", "hint": "try --help"}}
    assert captured.out == ""


def test_fail_plain_human_line(monkeypatch, capsys):
    monkeypatch.setattr(output.sys.stderr, "isatty", lambda: True, raising=False)
    with pytest.raises(SystemExit):
        fail("boom", "usage", "try --help", 2)
    captured = capsys.readouterr()
    assert "error[usage]: boom" in captured.err
    assert "hint: try --help" in captured.err


def test_fail_quiet_drops_hint(monkeypatch, capsys):
    monkeypatch.setenv("MYCLI_QUIET", "1")
    monkeypatch.setattr(output.sys.stderr, "isatty", lambda: True, raising=False)
    with pytest.raises(SystemExit):
        fail("boom", "usage", "try --help", 2)
    assert "hint:" not in capsys.readouterr().err
