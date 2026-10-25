"""
tests/test_demo_fixtures.py - Member 3 Test Battery Validation
Verifies all 8 canonical PR archetypes specified in WORK_DIVISION.md.
"""

import pytest
from demo.fixtures import load_all_demo_prs, load_demo_pr, load_raw_fixture
from ai.reviewer import AIReviewer


@pytest.fixture
def reviewer():
    return AIReviewer(prefer_ollama=False)


def test_load_all_eight_fixtures():
    prs = load_all_demo_prs()
    assert len(prs) == 8
    for i, pr in enumerate(prs, start=1):
        assert pr.pr_id == i
        assert len(pr.files) >= 1
        assert pr.author != ""
        assert pr.title != ""


def test_scenario_1_good_auth_fix(reviewer):
    pr = load_demo_pr(1)
    res = reviewer.review(pr)
    assert res.verdict == "Looks good"
    assert not res.is_suspicious_injection
    assert res.confidence_score >= 0.90


def test_scenario_2_beginner_mistake(reviewer):
    pr = load_demo_pr(2)
    res = reviewer.review(pr)
    assert res.verdict == "Needs work"
    assert not res.is_suspicious_injection
    assert "unit tests" in res.draft_reply.lower()


def test_scenario_3_whitespace_spam(reviewer):
    pr = load_demo_pr(3)
    res = reviewer.review(pr)
    assert res.verdict == "Likely junk"
    assert not res.is_suspicious_injection


def test_scenario_4_claim_mismatch(reviewer):
    pr = load_demo_pr(4)
    res = reviewer.review(pr)
    assert res.verdict == "Likely junk"
    assert not res.is_suspicious_injection
    assert "claim" in res.short_reason.lower() or "discrepancy" in res.draft_reply.lower()


def test_scenario_5_empty_description(reviewer):
    pr = load_demo_pr(5)
    res = reviewer.review(pr)
    assert res.verdict == "Needs work"
    assert not res.is_suspicious_injection
    assert "description" in res.short_reason.lower()


def test_scenario_6_failing_ci(reviewer):
    pr = load_demo_pr(6)
    res = reviewer.review(pr)
    assert res.verdict == "Needs work"
    assert not res.is_suspicious_injection
    assert "ci" in res.short_reason.lower() or "pipeline" in res.draft_reply.lower()


def test_scenario_7_prompt_injection_blocked(reviewer):
    pr = load_demo_pr(7)
    res = reviewer.review(pr)
    assert res.verdict == "Likely junk"
    assert res.is_suspicious_injection is True
    assert "[SECURITY ALERT" in res.short_reason
    assert "adversarial" in res.short_reason.lower() or "injection" in res.short_reason.lower()


def test_scenario_8_doc_improvement(reviewer):
    pr = load_demo_pr(8)
    res = reviewer.review(pr)
    assert res.verdict == "Looks good"
    assert not res.is_suspicious_injection
    assert "documentation" in res.short_reason.lower()
