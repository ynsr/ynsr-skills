"""Tests for auto_review.py inline synthesis (findings without inline entries)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from auto_review import ordered_inline  # noqa: E402


def test_ordered_inline_synthesizes_missing_nit_entry():
    findings = {"blockers": [], "important": [],
                "nits": [{"issue": "Whitespace realignment", "file": "a/F.java",
                          "line": 55, "details": "Adds diff noise",
                          "fix": "Avoid realignment"}],
                "inline_comments": []}
    inlines = ordered_inline(findings, 10)
    assert len(inlines) == 1
    assert inlines[0]["file"] == "a/F.java"
    assert inlines[0]["line"] == 55
    assert "Adds diff noise" in inlines[0]["comment"]


def test_ordered_inline_does_not_duplicate_existing_entry():
    findings = {"blockers": [], "important": [], "nits": [],
                "inline_comments": [{"file": "a/F.java", "line": 55,
                                     "comment": "Existing note"}]}
    inlines = ordered_inline(findings, 10)
    assert len(inlines) == 1
    assert inlines[0]["comment"] == "Existing note"


def test_ordered_inline_blockers_sort_before_nits():
    findings = {"blockers": [{"issue": "B", "file": "b.java", "line": 1,
                              "details": "d"}],
                "important": [],
                "nits": [{"issue": "N", "file": "a.java", "line": 1,
                          "details": "d"}],
                "inline_comments": []}
    inlines = ordered_inline(findings, 10)
    assert [c["file"] for c in inlines] == ["b.java", "a.java"]


def test_synthesized_comment_dedupes_like_handwritten():
    finding = {"issue": "Whitespace realignment", "file": "a/F.java",
               "line": 55, "details": "Adds diff noise",
               "fix": "Avoid realignment"}
    first = ordered_inline({"blockers": [], "important": [], "nits": [finding],
                            "inline_comments": []}, 10)
    assert len(first) == 1
    rerun = ordered_inline({"blockers": [], "important": [], "nits": [finding],
                            "inline_comments": [first[0]]}, 10)
    assert len(rerun) == 1
    assert rerun[0]["comment"] == first[0]["comment"]
    key = lambda c: (c.get("file"), c.get("line"), (c.get("comment") or "")[:120])
    assert key(rerun[0]) == key(first[0])


def test_findings_without_file_line_stay_summary_only():
    findings = {"blockers": [], "important": [],
                "nits": [{"issue": "General nit", "details": "No location"}],
                "inline_comments": []}
    assert ordered_inline(findings, 10) == []
