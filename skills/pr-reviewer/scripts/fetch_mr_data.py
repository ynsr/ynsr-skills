#!/usr/bin/env python3
"""
Fetch GitLab merge request data using glab CLI and organize it for review.

Mirrors fetch_pr_data.py (GitHub): same output shape so the analyze/generate
steps stay platform-agnostic. Works with gitlab.com and self-hosted instances;
the host is derived from the MR URL and passed via `glab -R <project-url>`
because glab resolves the target instance from the git remote or -R flag.

Usage:
    python fetch_mr_data.py <mr_url> [--output-dir <dir>] [--no-clone]

Example:
    python fetch_mr_data.py https://git.jibit.cloud/server/ipg-commons/-/merge_requests/38
    python fetch_mr_data.py https://gitlab.com/group/proj/-/merge_requests/7 --no-clone

Default output: ~/dev/PRs/<group>_<project>/<IID>/ (override with --output-dir).
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from review_platform import ReviewTarget, default_reviews_base, parse_review_url, run_cli



def run_glab(args: List[str]) -> str:
    return run_cli(['glab'] + args, 'glab', 'https://gitlab.com/gitlab-org/cli')


def fetch_mr_metadata(target: ReviewTarget) -> Dict:
    """Fetch MR metadata using glab mr view."""
    output = run_glab(['mr', 'view', '-R', target.project_url,
                       target.number, '--output', 'json'])
    return json.loads(output)


def fetch_mr_diff(target: ReviewTarget) -> str:
    """Fetch MR diff using glab mr diff."""
    return run_glab(['mr', 'diff', '-R', target.project_url, target.number])


def fetch_mr_notes(target: ReviewTarget) -> List[Dict]:
    """Fetch all MR discussions/notes (inline + general comments)."""
    output = run_glab(['mr', 'note', 'list', '-R', target.project_url,
                       target.number, '-F', 'json'])
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def fetch_mr_commits(target: ReviewTarget, project_id: int) -> List[Dict]:
    """Fetch commit details for the MR via the projects API."""
    output = run_glab(['api', f'projects/{project_id}/merge_requests/{target.number}/commits',
                       '--hostname', target.host or ''])
    data = json.loads(output)
    return data if isinstance(data, list) else [data]


def extract_ticket_numbers(text: str) -> List[str]:
    """Extract ticket/issue references (#123, PROJ-123, IPG-721)."""
    tickets: List[str] = []
    for pattern in (r'#(\d+)', r'([A-Z]+-\d+)'):
        tickets.extend(re.findall(pattern, text))
    return list(set(tickets))


def setup_mr_review_dir(base_dir: str, project_path: str, number: str) -> Path:
    """Create and return the MR review directory (shared ~/dev/PRs tree)."""
    safe = project_path.replace('/', '_')
    pr_review_dir = Path(base_dir).expanduser() / 'PRs' / safe / number
    pr_review_dir.mkdir(parents=True, exist_ok=True)
    return pr_review_dir


def clone_mr_branch(target: ReviewTarget, source_branch: str, target_dir: Path) -> None:
    """Clone the MR source branch into target directory."""
    repo_url = f"git@{target.host}:{target.project_path}.git"
    clone_dir = target_dir / "source"
    if clone_dir.exists():
        print(f"Repository already cloned at {clone_dir}, pulling latest...")
        subprocess.run(['git', '-C', str(clone_dir), 'pull'], check=True)
    else:
        print(f"Cloning {repo_url} branch {source_branch}...")
        subprocess.run(['git', 'clone', '--branch', source_branch,
                        '--single-branch', repo_url, str(clone_dir)], check=True)


def save_data(mr_review_dir: Path, data: Dict) -> None:
    for filename, content in data.items():
        filepath = mr_review_dir / filename
        if filename.endswith('.json'):
            with open(filepath, 'w') as f:
                json.dump(content, f, indent=2)
        else:
            with open(filepath, 'w') as f:
                f.write(content)
        print(f"Saved: {filepath}")


def build_summary(target: ReviewTarget, metadata: Dict, commits: List[Dict],
                  notes: List[Dict], tickets: List[str], mr_review_dir: Path) -> str:
    author = metadata.get('author', {})
    return f"""MR Review Summary
==================

Platform: GitLab ({target.host})
Project: {target.project_path}
MR IID: !{target.number}
Title: {metadata.get('title', 'N/A')}
Author: {author.get('username', author.get('name', 'N/A'))}
State: {metadata.get('state', 'N/A')}
Draft: {metadata.get('draft', metadata.get('work_in_progress', False))}

Branches:
  Source: {metadata.get('source_branch', 'N/A')}
  Target: {metadata.get('target_branch', 'N/A')}

Commits: {len(commits)}
Discussions: {len(notes)}

Related Tickets:
{chr(10).join(f"  - {t}" for t in tickets) if tickets else "  None found"}

Review Directory: {mr_review_dir}
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Fetch GitLab MR data for code review',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    parser.add_argument('mr_url', help='GitLab MR URL (.../-/merge_requests/<iid>)')
    parser.add_argument('--output-dir', default=default_reviews_base(),
                        help='Base output directory (default: ~/dev)')
    parser.add_argument('--no-clone', action='store_true', help='Skip cloning the repository')
    args = parser.parse_args()

    try:
        target = parse_review_url(args.mr_url)
        if target.platform != "gitlab":
            raise ValueError(f"Not a GitLab MR URL: {args.mr_url}. Use fetch_pr_data.py for GitHub.")
        print(f"Fetching MR !{target.number} from {target.host}/{target.project_path}...")

        mr_review_dir = setup_mr_review_dir(args.output_dir, target.project_path, target.number)
        print(f"MR review directory: {mr_review_dir}")

        print("Fetching MR metadata...")
        metadata = fetch_mr_metadata(target)

        print("Fetching MR diff...")
        diff = fetch_mr_diff(target)

        print("Fetching MR discussions...")
        try:
            notes = fetch_mr_notes(target)
        except RuntimeError as e:
            print(f"Warning: could not fetch discussions: {e}")
            notes = []

        print("Fetching commit history...")
        commits = fetch_mr_commits(target, metadata.get('project_id'))

        print("Extracting ticket references...")
        all_text = f"{metadata.get('title', '')} {metadata.get('description', '')}"
        for commit in commits:
            all_text += f" {commit.get('title', '')} {commit.get('message', '')}"
        tickets = extract_ticket_numbers(all_text)

        if not args.no_clone:
            try:
                print("Cloning repository...")
                clone_mr_branch(target, metadata['source_branch'], mr_review_dir)
            except Exception as e:
                print(f"Warning: Could not clone repository: {e}")

        print("\nSaving data...")
        platform_info = {
            'platform': 'gitlab',
            'host': target.host,
            'project_path': target.project_path,
            'project_url': target.project_url,
            'number': target.number,
            'repository': target.project_path,
            'title': metadata.get('title'),
            'author': (metadata.get('author') or {}).get('username'),
            'head_branch': metadata.get('source_branch'),
            'base_branch': metadata.get('target_branch'),
        }
        save_data(mr_review_dir, {
            'platform.json': platform_info,
            'metadata.json': metadata,
            'diff.patch': diff,
            'notes.json': notes,
            'commits.json': commits,
            'ticket_numbers.json': tickets,
        })

        summary = build_summary(target, metadata, commits, notes, tickets, mr_review_dir)
        with open(mr_review_dir / 'SUMMARY.txt', 'w') as f:
            f.write(summary)
        print(f"\n{summary}\nAll data saved to: {mr_review_dir}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
