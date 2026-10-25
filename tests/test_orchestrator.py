"""
Unit tests for Pipeline Orchestrator.
"""

from core.github_client import GitHubClient
from core.db import ShieldDatabase
from core.orchestrator import ShieldOrchestrator
from core.schemas import VisualizerData, AIReviewResult


def test_orchestrator_pipeline_with_mock(tmp_path):
    test_db_file = str(tmp_path / "test_orchestrator.sqlite3")
    db = ShieldDatabase(db_path=test_db_file)
    orchestrator = ShieldOrchestrator(db=db)

    # Register mock hooks for Member 2 and Member 3
    orchestrator.register_visualizer_handler(
        lambda ctx: VisualizerData(mermaid_diagram="graph TD;\nA-->B;", treemap_nodes=[])
    )
    orchestrator.register_ai_review_handler(
        lambda ctx: AIReviewResult(
            verdict="Looks good",
            short_reason="Valid patch with tests",
            draft_reply="Thanks for the clean contribution!",
            is_suspicious_injection=False,
            confidence_score=0.95
        )
    )

    mock_pr = GitHubClient.create_mock_pr(pr_id=99, title="Awesome feature", description="Closes #1")
    context = orchestrator.process_pr("mock/repo#99", persist=True, mock_context=mock_pr)

    assert context.quick_checks is not None
    assert context.visualization is not None
    assert context.visualization.mermaid_diagram == "graph TD;\nA-->B;"
    assert context.ai_review is not None
    assert context.ai_review.verdict == "Looks good"

    # Verify saved in DB
    saved_pr = db.get_pr(99)
    assert saved_pr is not None
    assert saved_pr.ai_review.verdict == "Looks good"
