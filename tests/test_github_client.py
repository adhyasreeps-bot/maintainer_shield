"""
Unit tests for GitHub Client & Identifier Parsing.
"""

import pytest
from core.github_client import GitHubClient


def test_parse_pr_identifier():
    # Full URL
    owner, repo, pr = GitHubClient.parse_pr_identifier("https://github.com/torvalds/linux/pull/1234")
    assert owner == "torvalds"
    assert repo == "linux"
    assert pr == 1234

    # Without protocol
    owner, repo, pr = GitHubClient.parse_pr_identifier("github.com/psf/requests/pull/99")
    assert owner == "psf"
    assert repo == "requests"
    assert pr == 99

    # Shorthand owner/repo#pr
    owner, repo, pr = GitHubClient.parse_pr_identifier("pallets/flask#456")
    assert owner == "pallets"
    assert repo == "flask"
    assert pr == 456

    # Invalid string
    with pytest.raises(ValueError):
        GitHubClient.parse_pr_identifier("invalid_string_without_pr")


def test_mock_pr_creation():
    mock_ctx = GitHubClient.create_mock_pr(
        pr_id=77,
        title="test PR",
        description="A test description",
        author="test-user"
    )
    assert mock_ctx.pr_id == 77
    assert mock_ctx.author == "test-user"
    assert len(mock_ctx.files) == 1
    assert mock_ctx.files[0].filename == "README.md"
