"""
Unit tests for Stage 1 Quick Checks Engine.
"""

from core.schemas import FileChange, categorize_file
from core.quick_checks import QuickChecksEngine, run_quick_checks


def test_categorize_file():
    assert categorize_file("tests/unit/test_auth.py") == "tests"
    assert categorize_file("src/component.spec.ts") == "tests"
    assert categorize_file("README.md") == "docs"
    assert categorize_file("docs/index.rst") == "docs"
    assert categorize_file("package.json") == "config"
    assert categorize_file(".github/workflows/ci.yml") == "config"
    assert categorize_file("src/models/user.py") == "core"
    assert categorize_file("assets/logo.png") == "other"


def test_empty_and_placeholder_description():
    # Empty
    has_desc, length, flags = QuickChecksEngine.check_description("")
    assert not has_desc
    assert "MISSING_DESCRIPTION" in flags

    # Whitespace only
    has_desc, length, flags = QuickChecksEngine.check_description("   \n  ")
    assert not has_desc
    assert "EMPTY_DESCRIPTION" in flags

    # Placeholder word
    has_desc, length, flags = QuickChecksEngine.check_description("fix")
    assert not has_desc
    assert "PLACEHOLDER_DESCRIPTION" in flags

    # Unedited template
    has_desc, length, flags = QuickChecksEngine.check_description("<!-- Describe your changes here -->")
    assert "UNEDITED_TEMPLATE" in flags


def test_issue_link_extraction():
    text = "This closes #142 and also fixes #99 and relates to https://github.com/org/repo/issues/50"
    links = QuickChecksEngine.extract_issue_links(text)
    assert "#142" in links
    assert "#99" in links
    assert "#50" in links

    no_links = QuickChecksEngine.extract_issue_links("Just a random commit with no issue")
    assert len(no_links) == 0


def test_whitespace_only_detection():
    patch = "@@ -1,3 +1,3 @@\n-line one\n+line one   \n"
    assert QuickChecksEngine.is_diff_whitespace_only(patch) is True

    substantive_patch = "@@ -1,3 +1,3 @@\n-return False\n+return True\n"
    assert QuickChecksEngine.is_diff_whitespace_only(substantive_patch) is False


def test_trivial_typo_diff():
    file = FileChange(
        filename="README.md",
        category="docs",
        additions=1,
        deletions=1,
        status="modified",
        patch="@@ -1,3 +1,3 @@\n-Teh quick brown fox\n+The quick brown fox\n"
    )
    is_trivial, flags = QuickChecksEngine.check_diff_triviality([file])
    assert is_trivial is True
    assert "TRIVIAL_TYPO_DIFF" in flags


def test_full_quick_check_pipeline():
    # Good PR
    good_files = [
        FileChange(filename="src/auth.py", category="core", additions=20, deletions=5),
        FileChange(filename="tests/test_auth.py", category="tests", additions=30, deletions=0)
    ]
    res_good = run_quick_checks(
        title="feat: add OAuth2 refresh token support (Fixes #10)",
        description="Implements token refresh handling when expired. Fixes #10.",
        files=good_files,
        ci_status="passed",
    )
    assert res_good.has_description is True
    assert res_good.has_issue_link is True
    assert res_good.is_whitespace_or_typo_only is False
    assert res_good.ci_status == "passed"
    assert res_good.score == 100

    # Low-effort PR
    spam_files = [
        FileChange(filename="README.md", category="docs", additions=1, deletions=1, patch="@@ -1 +1 @@\n-a\n+a \n")
    ]
    res_spam = run_quick_checks(
        title="update",
        description="",
        files=spam_files,
        ci_status="none",
    )
    assert res_spam.has_description is False
    assert res_spam.is_whitespace_or_typo_only is True
    assert "MISSING_DESCRIPTION" in res_spam.flags
    assert "NO_ISSUE_LINK" in res_spam.flags
    assert "WHITESPACE_ONLY_DIFF" in res_spam.flags
    assert res_spam.score < 50
