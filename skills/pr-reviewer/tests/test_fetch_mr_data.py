"""Tests for scripts/fetch_mr_data.py (pure helpers; no network/CLI)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pytest  # noqa: E402

from fetch_mr_data import (  # noqa: E402
    build_summary,
    extract_ticket_numbers,
    setup_mr_review_dir,
)
from review_platform import parse_review_url  # noqa: E402


def test_extract_ticket_numbers_gitlab_style():
    tickets = extract_ticket_numbers("Closes IPG-721, see also #38 and PROJ-9")
    assert "IPG-721" in tickets
    assert "38" in tickets
    assert "PROJ-9" in tickets


def test_extract_ticket_numbers_dedupes():
    assert extract_ticket_numbers("IPG-721 IPG-721") == ["IPG-721"]


def test_setup_mr_review_dir_sanitizes_subgroups(tmp_path):
    d = setup_mr_review_dir(str(tmp_path), "group/sub/proj", "38")
    assert d == tmp_path / "PRs" / "group_sub_proj" / "38"
    assert d.is_dir()


def test_build_summary_gitlab_fields(tmp_path):
    target = parse_review_url("https://git.jibit.cloud/server/ipg-commons/-/merge_requests/38")
    metadata = {"title": "T", "author": {"username": "younes"}, "state": "opened",
                "draft": True, "source_branch": "feat", "target_branch": "develop"}
    summary = build_summary(target, metadata, [{}, {}], [{}], ["IPG-721"], tmp_path)
    assert "GitLab (git.jibit.cloud)" in summary
    assert "MR IID: !38" in summary
    assert "Commits: 2" in summary
    assert "IPG-721" in summary


def test_fetch_rejects_github_url(monkeypatch):
    """fetch_mr_data.main must refuse GitHub URLs (fetch_pr_data.py owns those)."""
    import fetch_mr_data
    monkeypatch.setattr(sys, "argv", ["fetch_mr_data.py", "https://github.com/o/r/pull/1"])
    with pytest.raises(SystemExit) as exc:
        fetch_mr_data.main()
    assert exc.value.code == 1


def test_module_annotations_resolve_eagerly():
    """Regression: all typing names (List/Dict) must be imported so that
    function annotations resolve even under eager/lazy evaluation."""
    import fetch_mr_data
    import typing
    for name in ("run_glab", "fetch_mr_metadata", "fetch_mr_diff",
                 "fetch_mr_notes", "fetch_mr_commits", "extract_ticket_numbers",
                 "setup_mr_review_dir", "clone_mr_branch", "save_data",
                 "build_summary", "main"):
        fn = getattr(fetch_mr_data, name)
        assert isinstance(typing.get_type_hints(fn), dict)
