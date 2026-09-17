#!/usr/bin/env python3
"""
Shared platform helpers for the pr-reviewer skill.

Supports GitHub pull requests and GitLab merge requests (gitlab.com and
self-hosted instances). URL parsing is pure logic; CLI invocation helpers
shell out to `gh` (GitHub) or `glab` (GitLab).

GitLab host resolution: `glab` resolves the target instance from the git
remote of the current repo or from a `-R <project-url>` flag. Bare
`server/project` paths outside a clone hit the default host (usually
gitlab.com), so scripts MUST pass the full project URL derived from the MR
URL, e.g. `-R https://git.jibit.cloud/server/ipg-commons`.
"""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def default_reviews_base() -> str:
    """Default base output directory for fetched review data (`~/dev`)."""
    return str(Path.home() / "dev")


@dataclass(frozen=True)
class ReviewTarget:
    """Parsed review URL. `number` is the PR number (GitHub) or MR iid (GitLab)."""
    platform: str  # "github" | "gitlab"
    number: str
    # GitHub
    owner: Optional[str] = None
    repo: Optional[str] = None
    # GitLab
    host: Optional[str] = None
    project_path: Optional[str] = None  # e.g. "server/ipg-commons" (subgroups supported)

    @property
    def repo_spec(self) -> str:
        """Short spec: owner/repo (GitHub) or project path (GitLab)."""
        if self.platform == "github":
            return f"{self.owner}/{self.repo}"
        return self.project_path or ""

    @property
    def project_url(self) -> str:
        """Full project URL for `glab -R`. Only meaningful for GitLab."""
        if self.platform != "gitlab":
            raise ValueError("project_url is only defined for GitLab targets")
        return f"https://{self.host}/{self.project_path}"

    @property
    def display(self) -> str:
        if self.platform == "github":
            return f"{self.owner}/{self.repo}#{self.number}"
        return f"{self.host}/{self.project_path}!{self.number}"


_GITHUB_RE = re.compile(
    r"github\.com[/:](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/pull/(?P<number>\d+)"
)
_GITLAB_RE = re.compile(
    r"https?://(?P<host>[^/]+)/(?P<project>.+?)/-/merge_requests/(?P<iid>\d+)"
)


def parse_review_url(url: str) -> ReviewTarget:
    """
    Parse a GitHub PR URL or GitLab MR URL into a ReviewTarget.

    GitHub: https://github.com/<owner>/<repo>/pull/<number>
    GitLab:  https://<host>/<group>[/<subgroup>...]/<project>/-/merge_requests/<iid>

    Raises:
        ValueError: If the URL matches neither shape.
    """
    url = url.strip().rstrip("/")
    m = _GITHUB_RE.search(url)
    if m:
        return ReviewTarget(
            platform="github",
            owner=m.group("owner"),
            repo=m.group("repo"),
            number=m.group("number"),
        )
    m = _GITLAB_RE.search(url)
    if m:
        return ReviewTarget(
            platform="gitlab",
            host=m.group("host"),
            project_path=m.group("project"),
            number=m.group("iid"),
        )
    raise ValueError(
        f"Unrecognized review URL: {url!r}. Expected a GitHub .../pull/<n> "
        "or GitLab .../-/merge_requests/<iid> URL."
    )


def run_cli(cmd: list, tool: str, install_hint: str) -> str:
    """Run a `gh`/`glab` command, returning stdout. Raises RuntimeError on failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"{tool} command failed: {e.stderr.strip() or e}")
    except FileNotFoundError:
        raise RuntimeError(f"{tool} CLI not found. Please install: {install_hint}")
