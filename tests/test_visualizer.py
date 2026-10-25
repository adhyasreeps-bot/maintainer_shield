"""
tests/test_visualizer.py - Member 2 Unit Tests
Validates Diagram Generator, Claim vs Reality Comparator,
Commit Graph hygiene checks, and Web API routes.
"""

import pytest
from core.schemas import FileChange, PRShieldContext
from visualizer.diagram_generator import (
    generate_treemap_data,
    generate_mermaid_flowchart,
    build_visualizer_data,
    generate_visualizer_data,
)
from visualizer.claim_reality import analyze_claim_vs_reality
from visualizer.commit_graph import detect_commit_patterns, generate_commit_timeline
from fastapi.testclient import TestClient
from web.app import app


def test_treemap_percentage_calculation():
    files = [
        FileChange(filename="src/core.py", category="core", additions=70, deletions=30),
        FileChange(filename="docs/README.md", category="docs", additions=10, deletions=0),
    ]
    nodes, percentages = generate_treemap_data(files)
    assert len(nodes) == 2
    assert percentages["core"] == 90.9
    assert percentages["docs"] == 9.1


def test_mermaid_generation():
    files = [
        FileChange(filename="src/app.py", category="core", additions=10, deletions=5),
        FileChange(filename="tests/test_app.py", category="tests", additions=20, deletions=0),
    ]
    diag = generate_mermaid_flowchart(files)
    assert "flowchart TD" in diag
    assert "subgraph sg_core" in diag
    assert "subgraph sg_tests" in diag


def test_claim_vs_reality_mismatch_detection():
    # Scenario 4 from blueprint: Claims doc typo, but touches auth.py
    title = "Fix docs typo in installation section"
    description = "Just fixing a minor typo in documentation."
    files = [FileChange(filename="src/api/auth.py", category="core", additions=15, deletions=2)]

    res = analyze_claim_vs_reality(title, description, files)
    assert res["is_mismatch"] is True
    assert res["severity"] == "high"
    assert "docs" in res["claimed"]
    assert res["actual"] == "core"


def test_claim_vs_reality_match():
    title = "docs: update API documentation"
    description = "Updated getting started guide."
    files = [FileChange(filename="docs/api.md", category="docs", additions=50, deletions=2)]

    res = analyze_claim_vs_reality(title, description, files)
    assert res["is_mismatch"] is False
    assert res["severity"] == "none"


def test_commit_pattern_squash_warning():
    # Scenario 2 from blueprint: commits named fix, fix2, update
    commits = [
        {"sha": "111", "message": "fix"},
        {"sha": "222", "message": "fix2"},
        {"sha": "333", "message": "update"},
    ]
    warnings, squash_rec = detect_commit_patterns(commits)
    assert squash_rec is True
    assert len(warnings) >= 1
    assert "squash" in warnings[0].lower()


def test_clean_commits():
    commits = [
        {"sha": "abc", "message": "feat(auth): add OAuth2 provider"},
    ]
    warnings, squash_rec = detect_commit_patterns(commits)
    assert squash_rec is False
    assert len(warnings) == 0


def test_web_dashboard_endpoints():
    client = TestClient(app)
    # Test GET index
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Maintainer Shield" in resp.text

    # Test GET PRs API
    resp = client.get("/api/prs")
    assert resp.status_code == 200
    prs = resp.json()
    assert len(prs) >= 8

    # Test GET PR detail
    resp = client.get("/api/prs/1")
    assert resp.status_code == 200
    assert resp.json()["pr_id"] == 1


def test_scan_api_endpoint_validation():
    client = TestClient(app)
    resp = client.post("/api/scan", json={"target": "invalid_no_slash"})
    assert resp.status_code == 400
