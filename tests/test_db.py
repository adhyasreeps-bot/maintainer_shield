"""
Unit tests for Shield SQLite Database.
"""

import os
from core.github_client import GitHubClient
from core.schemas import QuickCheckResults
from core.db import ShieldDatabase


def test_db_lifecycle(tmp_path):
    test_db_file = str(tmp_path / "test_shield.sqlite3")
    db = ShieldDatabase(db_path=test_db_file)

    mock_pr = GitHubClient.create_mock_pr(pr_id=42, title="Bugfix PR", description="Fixing a bug")
    mock_pr.quick_checks = QuickCheckResults(
        has_description=True,
        description_length=15,
        has_issue_link=False,
        is_whitespace_or_typo_only=False,
        ci_status="passed",
        flags=["NO_ISSUE_LINK"],
        score=85,
        summary="Passed with warnings",
    )

    # 1. Save PR
    row_id = db.save_pr(mock_pr)
    assert row_id > 0

    # 2. Get PR by ID
    loaded = db.get_pr(42, "test-org/example-repo")
    assert loaded is not None
    assert loaded.pr_id == 42
    assert loaded.title == "Bugfix PR"
    assert loaded.quick_checks.score == 85

    # 3. List PRs
    prs = db.list_prs()
    assert len(prs) == 1
    assert prs[0]["pr_id"] == 42
    assert "NO_ISSUE_LINK" in prs[0]["quick_check_flags"]

    # 4. Record action
    action_id = db.record_action(42, "test-org/example-repo", "comment", comment_body="LGTM", labels=["needs-work"])
    assert action_id > 0

    history = db.get_action_history(42)
    assert len(history) == 1
    assert history[0]["action_type"] == "comment"
    assert history[0]["comment_body"] == "LGTM"
