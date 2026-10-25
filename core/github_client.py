"""
GitHub API Client for Maintainer Shield.
Handles pulling PR metadata, diffs, files, commit history, and CI check statuses,
as well as dispatching maintainer comments and labels back to GitHub.
Includes built-in offline/mock support for tests and demos.
"""

import os
import re
from typing import List, Dict, Tuple, Optional, Any
import requests

from core.schemas import FileChange, PRShieldContext, categorize_file


class GitHubClient:
    """Client for GitHub REST API v3."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("GITHUB_TOKEN", "").strip()
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Maintainer-Shield-Bot/1.0",
        })
        if self.token:
            self.session.headers["Authorization"] = f"token {self.token}"

    @staticmethod
    def parse_pr_identifier(identifier: str) -> Tuple[str, str, int]:
        """Parses a PR URL or shorthand 'owner/repo#123' into (owner, repo, pr_number).

        Supports formats:
        - https://github.com/owner/repo/pull/123
        - github.com/owner/repo/pull/123
        - owner/repo#123
        - owner/repo/pull/123
        """
        identifier = identifier.strip()

        # Match full URL
        url_match = re.search(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", identifier)
        if url_match:
            return url_match.group(1), url_match.group(2), int(url_match.group(3))

        # Match shorthand owner/repo#123
        shorthand_match = re.match(r"^([^/]+)/([^#]+)#(\d+)$", identifier)
        if shorthand_match:
            return shorthand_match.group(1), shorthand_match.group(2), int(shorthand_match.group(3))

        # Match owner/repo/pull/123
        alt_match = re.match(r"^([^/]+)/([^/]+)/pull/(\d+)$", identifier)
        if alt_match:
            return alt_match.group(1), alt_match.group(2), int(alt_match.group(3))

        raise ValueError(f"Invalid PR identifier or URL format: '{identifier}'")

    def list_prs(self, owner: str, repo: str, state: str = "open", limit: int = 10) -> List[int]:
        """Fetches list of pull request numbers for a repository."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls?state={state}&per_page={min(limit, 100)}"
        response = self.session.get(url, timeout=15)
        response.raise_for_status()
        raw_prs = response.json()
        return [pr["number"] for pr in raw_prs[:limit]]

    def get_pr_metadata(self, owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        """Fetches PR metadata from GitHub."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}"
        response = self.session.get(url, timeout=15)
        response.raise_for_status()
        return response.json()

    def get_pr_files(self, owner: str, repo: str, pr_number: int) -> List[FileChange]:
        """Fetches list of files changed in the PR and categorizes them."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        response = self.session.get(url, timeout=15)
        response.raise_for_status()

        raw_files = response.json()
        files: List[FileChange] = []
        for f in raw_files:
            filename = f.get("filename", "")
            files.append(FileChange(
                filename=filename,
                category=categorize_file(filename),
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
                status=f.get("status", "modified"),
                patch=f.get("patch"),
                raw_url=f.get("raw_url"),
            ))
        return files

    def get_pr_commits(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """Fetches commit history for the PR."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/commits"
        response = self.session.get(url, timeout=15)
        response.raise_for_status()

        raw_commits = response.json()
        commits = []
        for c in raw_commits:
            commit_obj = c.get("commit", {})
            commits.append({
                "sha": c.get("sha", "")[:7],
                "full_sha": c.get("sha", ""),
                "author": commit_obj.get("author", {}).get("name", "Unknown"),
                "message": commit_obj.get("message", "").strip(),
                "date": commit_obj.get("author", {}).get("date", ""),
            })
        return commits

    def get_pr_ci_status(self, owner: str, repo: str, head_sha: str) -> str:
        """Determines CI check status for the head commit ('passed', 'failed', 'pending', 'none')."""
        try:
            # 1. Check GitHub Actions Check Runs
            check_url = f"{self.BASE_URL}/repos/{owner}/{repo}/commits/{head_sha}/check-runs"
            resp = self.session.get(check_url, timeout=10)
            if resp.status_code == 200:
                check_runs = resp.json().get("check_runs", [])
                if check_runs:
                    conclusions = [c.get("conclusion") for c in check_runs if c.get("conclusion")]
                    if any(c in ["failure", "timed_out", "action_required"] for c in conclusions):
                        return "failed"
                    if any(c.get("status") in ["queued", "in_progress"] for c in check_runs):
                        return "pending"
                    if all(c in ["success", "neutral", "skipped"] for c in conclusions):
                        return "passed"

            # 2. Check Commit Statuses (legacy status API / third-party CIs)
            status_url = f"{self.BASE_URL}/repos/{owner}/{repo}/commits/{head_sha}/status"
            resp2 = self.session.get(status_url, timeout=10)
            if resp2.status_code == 200:
                state = resp2.json().get("state", "none")
                if state == "success":
                    return "passed"
                elif state == "failure":
                    return "failed"
                elif state == "pending":
                    return "pending"
        except Exception:
            # Fallback gracefully if CI status check encounters network or auth errors
            pass

        return "none"

    def fetch_full_pr(self, identifier: str) -> PRShieldContext:
        """Fetches all PR information and constructs a PRShieldContext object."""
        owner, repo, pr_number = self.parse_pr_identifier(identifier)
        metadata = self.get_pr_metadata(owner, repo, pr_number)
        files = self.get_pr_files(owner, repo, pr_number)
        commits = self.get_pr_commits(owner, repo, pr_number)
        head_sha = metadata.get("head", {}).get("sha", "")
        ci_status = self.get_pr_ci_status(owner, repo, head_sha) if head_sha else "none"

        return PRShieldContext(
            pr_id=pr_number,
            pr_url=metadata.get("html_url", f"https://github.com/{owner}/{repo}/pull/{pr_number}"),
            repo_name=f"{owner}/{repo}",
            author=metadata.get("user", {}).get("login", "unknown"),
            title=metadata.get("title", ""),
            raw_description=metadata.get("body", "") or "",
            head_branch=metadata.get("head", {}).get("ref", "unknown"),
            base_branch=metadata.get("base", {}).get("ref", "main"),
            commits=commits,
            files=files,
        )

    def post_comment(self, owner: str, repo: str, pr_number: int, body: str) -> Dict[str, Any]:
        """Dispatches an approved maintainer comment back to the GitHub PR."""
        if not self.token:
            raise ValueError("GitHub Token (GITHUB_TOKEN) is required to post comments.")
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{pr_number}/comments"
        resp = self.session.post(url, json={"body": body}, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def add_labels(self, owner: str, repo: str, pr_number: int, labels: List[str]) -> List[Dict[str, Any]]:
        """Applies labels to the PR."""
        if not self.token:
            raise ValueError("GitHub Token (GITHUB_TOKEN) is required to apply labels.")
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{pr_number}/labels"
        resp = self.session.post(url, json={"labels": labels}, timeout=15)
        resp.raise_for_status()
        return resp.json()

    @classmethod
    def create_mock_pr(
        cls,
        pr_id: int = 101,
        title: str = "docs: fix typo in README",
        description: str = "",
        files: Optional[List[FileChange]] = None,
        commits: Optional[List[Dict[str, Any]]] = None,
        ci_status: str = "passed",
        author: str = "novice-contributor",
        repo_name: str = "test-org/example-repo",
    ) -> PRShieldContext:
        """Utility method to instantiate a synthetic/mock PR for tests and offline demos."""
        if files is None:
            files = [
                FileChange(
                    filename="README.md",
                    category="docs",
                    additions=1,
                    deletions=1,
                    status="modified",
                    patch="@@ -1,3 +1,3 @@\n-Maintainer Sheild\n+Maintainer Shield\n",
                )
            ]
        if commits is None:
            commits = [{"sha": "a1b2c3d", "author": author, "message": "fix", "date": "2026-10-25T10:00:00Z"}]

        return PRShieldContext(
            pr_id=pr_id,
            pr_url=f"https://github.com/{repo_name}/pull/{pr_id}",
            repo_name=repo_name,
            author=author,
            title=title,
            raw_description=description,
            head_branch="patch-1",
            base_branch="main",
            commits=commits,
            files=files,
        )
