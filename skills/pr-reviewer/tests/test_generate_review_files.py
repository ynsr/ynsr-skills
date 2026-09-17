"""Tests for generate_review_files.py platform handling (GitHub + GitLab)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generate_review_files import (  # noqa: E402
    _post_command,
    _post_targets,
    generate_claude_commands,
    generate_inline_comments_file,
)

GH_META = {"platform": "github", "owner": "o", "repo": "r", "number": 123}
GL_META = {"platform": "gitlab", "host": "git.jibit.cloud",
           "project_path": "server/ipg-commons", "number": 38,
           "repository": "server/ipg-commons"}


def _comment(**kw):
    base = {"file": "a/Main.java", "line": 42, "comment": "Fix this",
            "code_snippet": "x = 1"}
    base.update(kw)
    return base


def test_github_post_command_backward_compatible():
    cmd = _post_command(_comment(owner="o", repo="r", pr_number=123), GH_META)
    assert cmd.startswith("python scripts/add_inline_comment.py o r 123 latest")


def test_github_post_command_falls_back_to_metadata():
    cmd = _post_command(_comment(), GH_META)
    assert "add_inline_comment.py o r 123 latest" in cmd


def test_gitlab_post_command_single_line():
    cmd = _post_command(_comment(), GL_META)
    assert 'python scripts/add_mr_note.py https://git.jibit.cloud/server/ipg-commons 38' in cmd
    assert '--file "a/Main.java" --line 42 -m "Fix this"' in cmd

def test_gitlab_post_command_range():
    cmd = _post_command(_comment(start_line=10, end_line=15), GL_META)
    assert "--line 10:15" in cmd


def test_gitlab_post_command_old_side():
    cmd = _post_command(_comment(side="LEFT"), GL_META)
    assert "--old-line 42" in cmd


def test_inline_file_uses_gitlab_commands():
    findings = {"summary": "s", "metadata": GL_META,
                "inline_comments": [_comment()]}
    content = generate_inline_comments_file(findings, GL_META)
    assert "add_mr_note.py" in content
    assert "add_inline_comment.py" not in content


def test_inline_file_uses_github_commands_by_default():
    findings = {"summary": "s", "metadata": GH_META,
                "inline_comments": [_comment(owner="o", repo="r", pr_number=123)]}
    content = generate_inline_comments_file(findings)
    assert "add_inline_comment.py" in content
    assert "add_mr_note.py" not in content


def test_post_targets_github_shape():
    t = _post_targets(GH_META)
    assert t["kind"] == "PR"
    assert "gh pr comment 123 --repo o/r" in t["post"]
    assert "--approve" in t["approve"]


def test_post_targets_gitlab_shape():
    t = _post_targets(GL_META)
    assert t["kind"] == "MR"
    assert "glab mr note create -R https://git.jibit.cloud/server/ipg-commons 38" in t["post"]
    assert "glab mr approve" in t["approve"]


def test_send_commands_gate_fixes(tmp_path):
    for meta in (GH_META, GL_META):
        d = tmp_path / meta["platform"]
        generate_claude_commands(d, meta)
        send = (d / ".claude" / "commands" / "send.md").read_text()
        decline = (d / ".claude" / "commands" / "send-decline.md").read_text()
        assert "STOP. Only fix code after the user explicitly approves fixes" in send
        assert "Never auto-commit on the\n   default branch" in decline
        assert "pr/inline.md" in send  # inline posting is part of /send


@pytest.fixture()
def findings_file(tmp_path):
    p = tmp_path / "findings.json"
    p.write_text(json.dumps({
        "summary": "ok", "metadata": GL_META,
        "inline_comments": [_comment()]}))
    return p


def test_end_to_end_gitlab_generation(tmp_path, findings_file):
    import generate_review_files as g
    review_dir = tmp_path / "review"
    review_dir.mkdir()
    argv = ["g", str(review_dir), "--findings", str(findings_file)]
    import sys as _sys
    _sys.argv = argv
    g.main()
    inline = (review_dir / "pr" / "inline.md").read_text()
    assert "add_mr_note.py" in inline
    assert (review_dir / "REVIEW_READY.txt").exists()
