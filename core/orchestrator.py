"""
Pipeline Orchestrator for Maintainer Shield.
Coordinates data flow from PR ingestion through Quick Checks, Visualizer (Member 2),
Ollama AI Review (Member 3), and Maintainer Action Dispatch.
"""

from typing import Optional, Callable
from core.schemas import PRShieldContext, VisualizerData, AIReviewResult
from core.github_client import GitHubClient
from core.quick_checks import QuickChecksEngine
from core.db import ShieldDatabase


class ShieldOrchestrator:
    """Central orchestrator managing the 4-stage Maintainer Shield pipeline."""

    def __init__(
        self,
        github_client: Optional[GitHubClient] = None,
        db: Optional[ShieldDatabase] = None,
    ):
        self.github_client = github_client or GitHubClient()
        self.db = db or ShieldDatabase()

        # Default hook for Member 2 (Visualizer)
        try:
            from visualizer.diagram_generator import generate_visualizer_data
            self.visualizer_handler: Optional[Callable[[PRShieldContext], VisualizerData]] = generate_visualizer_data
        except ImportError:
            self.visualizer_handler = None

        # Default hook for Member 3 (Ollama AI Reviewer)
        try:
            from ai.reviewer import review_pr
            self.ai_review_handler: Optional[Callable[[PRShieldContext], AIReviewResult]] = review_pr
        except ImportError:
            self.ai_review_handler = None

    def register_visualizer_handler(self, handler: Callable[[PRShieldContext], VisualizerData]) -> None:
        """Allows Member 2 to hook their Visualizer Engine into the pipeline."""
        self.visualizer_handler = handler

    def register_ai_review_handler(self, handler: Callable[[PRShieldContext], AIReviewResult]) -> None:
        """Allows Member 3 to hook their Ollama AI Reviewer into the pipeline."""
        self.ai_review_handler = handler

    def process_pr(
        self,
        pr_identifier: str,
        persist: bool = True,
        mock_context: Optional[PRShieldContext] = None
    ) -> PRShieldContext:
        """Executes the full pipeline for a PR:

        1. Ingest PR metadata, files, commits, CI status.
        2. Run Stage 1 Quick Checks.
        3. Run Stage 2 Visualizer (if registered).
        4. Run Stage 3 & 4 AI Review (if registered).
        5. Persist result in local SQLite DB.
        """
        # Step 1: Ingestion
        if mock_context:
            context = mock_context
        else:
            context = self.github_client.fetch_full_pr(pr_identifier)

        # Step 2: Stage 1 Quick Checks
        ci_status = "none"
        if context.quick_checks and context.quick_checks.ci_status:
            ci_status = context.quick_checks.ci_status

        context.quick_checks = QuickChecksEngine.evaluate(
            title=context.title,
            description=context.raw_description,
            files=context.files,
            ci_status=ci_status,
        )

        # Step 3: Stage 2 Visualizer hook (Member 2)
        if self.visualizer_handler:
            try:
                context.visualization = self.visualizer_handler(context)
            except Exception as e:
                # Log and fallback gracefully without failing the entire pipeline
                context.visualization = VisualizerData(
                    mermaid_diagram="",
                    commit_pattern_warnings=[f"Visualizer error: {str(e)}"]
                )

        # Step 4: Stage 3 & 4 AI Review hook (Member 3)
        if self.ai_review_handler:
            try:
                context.ai_review = self.ai_review_handler(context)
            except Exception as e:
                context.ai_review = AIReviewResult(
                    verdict="Needs work",
                    short_reason=f"AI Review unavailable: {str(e)}",
                    draft_reply="Could not generate automated reply at this time.",
                    confidence_score=0.0
                )

        # Step 5: Save to SQLite Database
        if persist:
            self.db.save_pr(context)

        return context

    def dispatch_maintainer_action(
        self,
        pr_id: int,
        repo_name: str,
        comment_body: Optional[str] = None,
        labels: Optional[list[str]] = None,
    ) -> dict:
        """Safely dispatches approved maintainer comments and labels to GitHub and logs action in SQLite."""
        results = {"comment_posted": False, "labels_applied": False, "errors": []}

        owner, repo = repo_name.split("/", 1)

        # 1. Post Comment if provided
        if comment_body:
            try:
                self.github_client.post_comment(owner, repo, pr_id, comment_body)
                results["comment_posted"] = True
                self.db.record_action(pr_id, repo_name, "comment", comment_body=comment_body, success=True)
            except Exception as e:
                results["errors"].append(f"Comment error: {str(e)}")
                self.db.record_action(pr_id, repo_name, "comment", comment_body=comment_body, success=False)

        # 2. Apply Labels if provided
        if labels:
            try:
                self.github_client.add_labels(owner, repo, pr_id, labels)
                results["labels_applied"] = True
                self.db.record_action(pr_id, repo_name, "label", labels=labels, success=True)
            except Exception as e:
                results["errors"].append(f"Labels error: {str(e)}")
                self.db.record_action(pr_id, repo_name, "label", labels=labels, success=False)

        return results
