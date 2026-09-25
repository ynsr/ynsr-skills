#!/usr/bin/env python3
"""Single-shot hands-off PR/MR review publisher.

Takes agent-produced findings JSON, fetches target metadata/diff to a temp
dir, renders the post body, then posts summary + verdict + inline notes with
no confirmation prompts. See ../SKILL.md for the verdict policy.

Usage:
    python auto_review.py <PR-or-MR-URL> --findings findings.json [--mode verdict|comment|strict]
    python auto_review.py <URL> --findings findings.json --dry-run --max-inline 5

Exit codes: 0 ok (incl. verdict=skip), 1 partial inline failure, 2 fetch/auth failure.
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PR_SCRIPTS = Path("/home/bs/projects/personal/ynsr-skills/skills/pr-reviewer/scripts")
sys.path.insert(0, str(PR_SCRIPTS))

from review_platform import parse_review_url  # noqa: E402
from generate_review_files import generate_human_review  # noqa: E402

SEVERITY_ORDER = ("blockers", "important", "nits")


def run(cmd: list, dry_run: bool, stdin_text: str | None = None) -> str:
    shown = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    if dry_run:
        print(f"DRY-RUN: {shown}")
        return ""
    try:
        r = subprocess.run(cmd, input=stdin_text, capture_output=True,
                           text=True, check=True)
        return r.stdout.strip()
    except FileNotFoundError:
        raise RuntimeError(f"CLI not found: {cmd[0]}")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"{shown} failed: {e.stderr.strip()}")


def decide_verdict(mode: str, counts: dict) -> str:
    """Map findings to approve|request-changes|comment. Never approves with blockers."""
    if counts["blockers"] > 0:
        return "request-changes" if mode == "strict" else "comment"
    if counts["important"] > 0:
        if mode == "strict":
            return "request-changes"
        return "comment"
    if mode == "comment":
        return "comment"
    return "approve"


def ordered_inline(findings: dict, cap: int) -> list:
    """Return inline_comments ordered blockers-first (by matching file/line)."""
    wanted = list(findings.get("inline_comments", [])[:cap * 3])
    sev_of = {}
    for sev in SEVERITY_ORDER:
        for item in findings.get(sev, []):
            sev_of[(item.get("file"), item.get("line"))] = SEVERITY_ORDER.index(sev)
    wanted.sort(key=lambda c: sev_of.get((c.get("file"), c.get("line")), 99))
    return wanted[:cap]


def fetch_metadata(target, workdir: Path) -> dict:
    """Fetch hosted metadata + diff for verdict context. Raises RuntimeError -> exit 2."""
    if target.platform == "github":
        repo = f"{target.owner}/{target.repo}"
        meta = json.loads(run(["gh", "pr", "view", target.number, "--repo", repo,
                               "--json", "title,author,headRefName,baseRefName,state,isDraft"],
                              dry_run=False))
        diff = run(["gh", "pr", "diff", target.number, "--repo", repo], dry_run=False)
        existing = json.loads(run(["gh", "api",
                                   f"/repos/{repo}/pulls/{target.number}/comments",
                                   "--paginate"], dry_run=False) or "[]")
        (workdir / "diff.patch").write_text(diff)
        return {"platform": "github", "owner": target.owner, "repo": target.repo,
                "number": int(target.number), "title": meta.get("title"),
                "state": meta.get("state"), "draft": meta.get("isDraft"),
                "existing_inline": existing}
    meta = json.loads(run(["glab", "mr", "view", "-R", target.project_url,
                           target.number, "--output", "json"], dry_run=False))
    diff = run(["glab", "mr", "diff", "-R", target.project_url, target.number],
               dry_run=False)
    (workdir / "diff.patch").write_text(diff)
    return {"platform": "gitlab", "host": target.host,
            "project_path": target.project_path,
            "project_url": target.project_url,
            "number": int(target.number), "title": meta.get("title"),
            "state": meta.get("state")}


def target_number(meta: dict) -> str:
    return str(meta["number"])


def post_github(meta: dict, body: str, verdict: str, inlines: list,
                dry_run: bool, workdir: Path) -> tuple[int, int]:
    repo = f"{meta['owner']}/{meta['repo']}"
    n, posted, skipped = target_number(meta), 0, 0
    body_file = workdir / "post_body.md"
    body_file.write_text(body)
    ref = (["--body-file", str(body_file)] if not dry_run
           else ["--body", body[:80] + "..."])
    run(["gh", "pr", "comment", n, "--repo", repo] + ref, dry_run)
    if verdict == "approve":
        run(["gh", "pr", "review", n, "--repo", repo, "--approve"], dry_run)
    elif verdict == "request-changes":
        run(["gh", "pr", "review", n, "--repo", repo, "--request-changes",
             "--body", "Automated review: blocking issues found (see comments)."],
            dry_run)
    sha = "" if dry_run else run(
        ["gh", "api", f"/repos/{repo}/pulls/{n}/commits", "--jq", ".[-1].sha"],
        dry_run)
    seen = {(c.get("path"), c.get("line"), (c.get("body") or "")[:120])
            for c in meta.get("existing_inline", [])}
    for c in inlines:
        key = (c.get("file"), c.get("line"), (c.get("comment") or "")[:120])
        if key in seen:  # idempotent re-run
            skipped += 1
            continue
        cmd = [sys.executable, str(PR_SCRIPTS / "add_inline_comment.py"),
               meta["owner"], meta["repo"], n, sha or "latest",
               c.get("file", "unknown"), str(c.get("line", 1)),
               c.get("comment", "")]
        if c.get("start_line"):
            cmd += ["--start-line", str(c["start_line"])]
        try:
            run(cmd, dry_run)
            posted += 1
        except RuntimeError as e:
            print(f"WARN inline failed {c.get('file')}:{c.get('line')}: {e}",
                  file=sys.stderr)
            skipped += 1
    return posted, skipped


def post_gitlab(meta: dict, body: str, verdict: str, inlines: list,
                dry_run: bool, workdir: Path) -> tuple[int, int]:
    url, iid = meta["project_url"], str(meta["number"])
    body_file = workdir / "post_body.md"
    body_file.write_text(body)
    if dry_run:
        run(["glab", "mr", "note", "create", "-R", url, iid, "-m",
             body[:80] + "..."], dry_run)
    else:
        run(["glab", "mr", "note", "create", "-R", url, iid,
             "--body-file", str(body_file)], dry_run)
    if verdict == "approve":
        run(["glab", "mr", "approve", "-R", url, iid], dry_run)
    # request-changes on GitLab: inline notes stay resolvable/blocking; no unapprove API.
    posted, skipped = 0, 0
    for c in inlines:
        cmd = [sys.executable, str(PR_SCRIPTS / "add_mr_note.py"), url, iid,
               "--file", c.get("file", "unknown"), "--unique", "--validate"]
        if c.get("side") == "LEFT" and not c.get("start_line"):
            cmd += ["--old-line", str(c.get("line", 1))]
        elif c.get("start_line") and c.get("end_line"):
            cmd += ["--line", f"{c['start_line']}:{c['end_line']}"]
        else:
            cmd += ["--line", str(c.get("line", 1))]
        cmd += ["-m", (c.get("comment") or "")[:80] if dry_run else c.get("comment", "")]
        try:
            run(cmd, dry_run)
            posted += 1
        except RuntimeError as e:
            print(f"WARN inline failed {c.get('file')}:{c.get('line')}: {e}",
                  file=sys.stderr)
            skipped += 1
    return posted, skipped


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", help="GitHub PR or GitLab MR URL")
    ap.add_argument("--findings", required=True, help="Findings JSON (pr-reviewer schema)")
    ap.add_argument("--mode", default="comment", choices=["comment", "verdict", "strict"])
    ap.add_argument("--max-inline", type=int, default=10)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-dir", action="store_true")
    args = ap.parse_args()

    try:
        findings = json.loads(Path(args.findings).read_text())
        counts = {k: len(findings.get(k, [])) for k in SEVERITY_ORDER}
        verdict = decide_verdict(args.mode, counts)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Error: bad findings file: {e}", file=sys.stderr)
        sys.exit(2)

    try:
        target = parse_review_url(args.url)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)

    workdir = Path(tempfile.mkdtemp(prefix="auto_review_"))
    posted, skipped = 0, 0
    failed_fetch = False
    try:
        if args.dry_run:
            meta = {"platform": target.platform, "owner": target.owner,
                    "repo": target.repo, "host": target.host,
                    "project_path": target.project_path,
                    "project_url": target.project_url if target.platform == "gitlab" else "",
                    "number": target.number, "existing_inline": []}
        else:
            try:
                meta = fetch_metadata(target, workdir)
            except RuntimeError as e:
                failed_fetch = True
                print(f"Error: fetch failed: {e}", file=sys.stderr)
                print(f"verdict=error url={args.url} workdir={workdir}")
                sys.exit(2)
            if str(meta.get("state", "")).lower() in ("closed", "merged"):
                print(f"verdict=skip blockers={counts['blockers']} "
                      f"important={counts['important']} posted=0 skipped=0 url={args.url}")
                return
        meta.setdefault("number", target.number)
        body = generate_human_review(findings, meta)
        (workdir / "human.md").write_text(body)
        (workdir / "receipt.json").write_text(json.dumps(
            {"url": args.url, "mode": args.mode, "verdict": verdict,
             "counts": counts}))
        inlines = ordered_inline(findings, args.max_inline)
        if meta["platform"] == "github":
            posted, skipped = post_github(meta, body, verdict, inlines,
                                          args.dry_run, workdir)
        else:
            posted, skipped = post_gitlab(meta, body, verdict, inlines,
                                          args.dry_run, workdir)
        print(f"verdict={verdict} blockers={counts['blockers']} "
              f"important={counts['important']} posted={posted} "
              f"skipped={skipped} url={args.url}")
        sys.exit(1 if skipped and not args.dry_run else 0)
    finally:
        if args.keep_dir or failed_fetch or (skipped and not args.dry_run):
            print(f"workdir kept: {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
