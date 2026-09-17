"""Unit tests for scripts/review_platform.py (no network, no CLI needed)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from review_platform import ReviewTarget, default_reviews_base, parse_review_url  # noqa: E402


def test_default_reviews_base_is_home_dev():
    import os
    assert default_reviews_base() == os.path.expanduser("~/dev")


def test_parse_github_pr_url():
    t = parse_review_url("https://github.com/facebook/react/pull/28476")
    assert t == ReviewTarget(platform="github", number="28476",
                             owner="facebook", repo="react")
    assert t.repo_spec == "facebook/react"
    assert t.display == "facebook/react#28476"


def test_parse_github_trailing_slash_and_git_suffix():
    t = parse_review_url("https://github.com/owner/repo.git/pull/123/")
    assert (t.owner, t.repo, t.number) == ("owner", "repo", "123")


def test_parse_gitlab_selfhosted_url():
    t = parse_review_url("https://git.jibit.cloud/server/projectx/-/merge_requests/1700")
    assert t == ReviewTarget(platform="gitlab", number="1700",
                             host="git.jibit.cloud", project_path="server/projectx")
    assert t.project_url == "https://git.jibit.cloud/server/projectx"
    assert t.display == "git.jibit.cloud/server/projectx!1700"


def test_parse_gitlab_nested_subgroups():
    t = parse_review_url("https://git.example.com/group/sub/deep/proj/-/merge_requests/42")
    assert t.host == "git.example.com"
    assert t.project_path == "group/sub/deep/proj"
    assert t.number == "42"


def test_parse_gitlab_dotcom_url():
    t = parse_review_url("https://gitlab.com/group/proj/-/merge_requests/7")
    assert (t.platform, t.host) == ("gitlab", "gitlab.com")


def test_parse_invalid_url_raises():
    with pytest.raises(ValueError, match="Unrecognized review URL"):
        parse_review_url("https://example.com/not-a-review/123")
    with pytest.raises(ValueError, match="Unrecognized review URL"):
        parse_review_url("https://github.com/owner/repo/issues/5")


def test_project_url_rejects_github():
    t = parse_review_url("https://github.com/o/r/pull/1")
    with pytest.raises(ValueError, match="only defined for GitLab"):
        _ = t.project_url
