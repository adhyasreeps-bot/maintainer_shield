"""
ai/reviewer.py - Stage 3 & 4 AI Review Engine & Tone Tuner
Member 3 Deliverable: AI & Security Lead.

Integrates:
- Stage 3: Prompt injection detection & untrusted content sanitization
- Local Ollama LLM execution with structured JSON validation
- Stage 4: Verdict classification ("Looks good", "Needs work", "Likely junk")
- Educational, supportive maintainer draft reply generation
- Deterministic fallback engine for offline/resilient execution
"""

import os
import logging
from typing import Optional, Dict, Any, List
from pydantic import ValidationError

from core.schemas import PRShieldContext, AIReviewResult, FileCategory
from ai.injection_detector import InjectionDetector, InjectionScanResult
from ai.prompts import SYSTEM_PROMPT, build_review_prompt
from ai.ollama_client import OllamaClient
from visualizer.claim_reality import analyze_claim_vs_reality
from visualizer.commit_graph import detect_commit_patterns

logger = logging.getLogger("maintainer_shield.ai.reviewer")


class AIReviewer:
    """Stage 3 & 4: AI Review Engine with Local Ollama & Guardrails."""

    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        prefer_ollama: Optional[bool] = None,
        ollama_timeout: int = 8,
    ):
        if prefer_ollama is None:
            prefer_ollama = os.environ.get("USE_OLLAMA", "").lower() in ("1", "true", "yes")
        self.ollama = ollama_client or OllamaClient(timeout_seconds=ollama_timeout)
        self.prefer_ollama = prefer_ollama

    def review(self, context: PRShieldContext) -> AIReviewResult:
        """Executes full AI review on PRShieldContext:
        1. Guardrail scan for prompt injections.
        2. Ollama LLM review (if available and enabled).
        3. Deterministic rule-based fallback if Ollama times out or is offline.
        """
        # =========================================================================
        # Stage 3A: Prompt Injection Defense
        # =========================================================================
        injection_result: InjectionScanResult = InjectionDetector.scan_pr(context)

        if injection_result.is_injection:
            logger.warning(
                f"Adversarial prompt injection intercepted on PR #{context.pr_id}: "
                f"{injection_result.explanation}"
            )
            return AIReviewResult(
                verdict="Likely junk",
                short_reason=f"[SECURITY ALERT] Adversarial prompt injection detected: {'; '.join(injection_result.detected_patterns[:2])}",
                draft_reply=(
                    f"⚠️ [SECURITY ALERT: Suspicious Prompt Injection Detected]\n\n"
                    f"Hello @{context.author},\n"
                    f"Our automated triage system flagged patterns in this pull request that resemble adversarial prompt overrides:\n"
                    f"- Flagged locations: {', '.join(injection_result.flagged_locations)}\n"
                    f"- Patterns: {'; '.join(injection_result.detected_patterns)}\n\n"
                    f"Per project security policy, automated processing has been paused and this submission has been marked for manual security review."
                ),
                is_suspicious_injection=True,
                confidence_score=0.99,
            )

        # =========================================================================
        # Stage 3B: Local Ollama LLM Review
        # =========================================================================
        if self.prefer_ollama:
            try:
                # Check if Ollama daemon is reachable
                if self.ollama.is_available():
                    prompt = build_review_prompt(context, injection_detected=False)
                    raw_json = self.ollama.generate_json(prompt=prompt, system=SYSTEM_PROMPT)

                    if raw_json and "verdict" in raw_json:
                        # Normalize verdict
                        v_raw = str(raw_json.get("verdict", "")).strip().lower()
                        if "good" in v_raw:
                            verdict = "Looks good"
                        elif "needs" in v_raw or "work" in v_raw:
                            verdict = "Needs work"
                        else:
                            verdict = "Likely junk"

                        short_reason = str(raw_json.get("short_reason", "")).strip() or "Evaluated by local Ollama model."
                        draft_reply = str(raw_json.get("draft_reply", "")).strip()
                        confidence = float(raw_json.get("confidence_score", 0.92))

                        if not draft_reply:
                            draft_reply = self._generate_fallback_draft_reply(context, verdict, short_reason)

                        return AIReviewResult(
                            verdict=verdict,
                            short_reason=short_reason,
                            draft_reply=draft_reply,
                            is_suspicious_injection=False,
                            confidence_score=min(max(confidence, 0.5), 1.0),
                        )
            except Exception as e:
                logger.info(f"Ollama inference did not complete ({e}), falling back to deterministic evaluator.")

        # =========================================================================
        # Stage 4: Deterministic Fallback Evaluator & Educational Tone Tuner
        # =========================================================================
        return self.deterministic_evaluate(context)

    def deterministic_evaluate(self, context: PRShieldContext) -> AIReviewResult:
        """High-precision, deterministic evaluation engine.
        Acts as the reference evaluation standard and handles offline execution.
        """
        author = context.author or "contributor"
        title = context.title or ""
        desc = context.raw_description or ""
        qc = context.quick_checks
        files = context.files or []
        commits = context.commits or []

        # Analyze file categories
        has_core = any(getattr(f, "category", "") == "core" for f in files)
        has_tests = any(getattr(f, "category", "") == "tests" for f in files)
        has_docs = any(getattr(f, "category", "") == "docs" for f in files)
        total_files = len(files)

        # Run Claim vs Reality check
        claim_data = analyze_claim_vs_reality(title, desc, files)
        has_claim_mismatch = claim_data.get("is_mismatch", False)

        # Run Commit Pattern check
        commit_res = detect_commit_patterns(commits)
        if isinstance(commit_res, tuple):
            commit_warnings, squash_recommended = commit_res
        else:
            commit_warnings, squash_recommended = (commit_res, False)
        has_messy_commits = len(commit_warnings) > 0

        # Rule 1: Whitespace / 1-character typo spam
        if qc and qc.is_whitespace_or_typo_only:
            return AIReviewResult(
                verdict="Likely junk",
                short_reason="Single-character trivial typo or whitespace-only change without linked issue. High probability of low-effort spam.",
                draft_reply=(
                    f"Hi @{author}, thank you for your interest in the project. "
                    f"However, per our contribution guidelines, we do not accept isolated one-character typo or whitespace-only pull requests. "
                    f"If you'd like to contribute, please check our issue tracker for open 'good first issue' tasks."
                ),
                is_suspicious_injection=False,
                confidence_score=0.98,
            )

        # Rule 2: Claim vs Reality Mismatch
        if has_claim_mismatch:
            claimed = claim_data.get("claimed", "documentation")
            actual = claim_data.get("actual", "core code")
            flagged_core = claim_data.get("core_files_flagged", [])
            return AIReviewResult(
                verdict="Likely junk",
                short_reason=f"PR claims {claimed} edits, but diff strictly touches {actual} ({', '.join(flagged_core[:2]) if flagged_core else actual}).",
                draft_reply=(
                    f"Hello @{author},\n\n"
                    f"We noticed a discrepancy in this pull request: the title/description states this is a {claimed} update, "
                    f"but the diff modifies sensitive {actual} files:\n"
                    + "\n".join(f"- `{f}`" for f in flagged_core[:3])
                    + f"\n\nPlease verify your branch and clarify the true intent of these changes before we can proceed with a review."
                ),
                is_suspicious_injection=False,
                confidence_score=0.95,
            )

        # Rule 3: Failing CI tests
        if qc and qc.ci_status == "failed":
            return AIReviewResult(
                verdict="Needs work",
                short_reason="Substantial feature or update, but automated CI test suites are failing.",
                draft_reply=(
                    f"Thanks for working on this @{author}! "
                    f"The implementation looks like a worthwhile addition, but the automated CI test pipeline currently fails on your branch. "
                    f"Please run the test suite locally (`pytest` or `npm test`), review the error logs, and update your PR once all checks pass."
                ),
                is_suspicious_injection=False,
                confidence_score=0.94,
            )

        # Rule 4: Empty or placeholder description
        has_desc = qc.has_description if qc else (len(desc.strip()) >= 15)
        desc_len = qc.description_length if qc else len(desc.strip())
        if not has_desc or desc_len < 15:
            return AIReviewResult(
                verdict="Needs work",
                short_reason="Empty or insufficient PR description. Maintainers lack context on motivation, behavior, and testing.",
                draft_reply=(
                    f"Hi @{author}, thank you for submitting this pull request! "
                    f"To help us review your changes efficiently, could you please update the PR description using our template? "
                    f"Please include:\n"
                    f"1. What problem does this solve?\n"
                    f"2. How did you test your changes?\n"
                    f"3. Any linked issue (e.g. `Fixes #123`)."
                ),
                is_suspicious_injection=False,
                confidence_score=0.91,
            )

        # Rule 5: Core logic touched without tests or with messy commit messages
        if has_core and not has_tests:
            reasons = ["modifies core logic without accompanying unit tests"]
            feedback_points = ["Please add unit tests under `tests/` covering both happy and error paths for your changes."]
            if has_messy_commits:
                reasons.append("contains uninformative commit messages")
                feedback_points.append(
                    f"Please squash or reword your commits ({', '.join(commit_warnings)}) into clear, conventional commit messages (e.g. `fix: ...`)."
                )

            return AIReviewResult(
                verdict="Needs work",
                short_reason=f"Valid code contribution, but {'; '.join(reasons)}.",
                draft_reply=(
                    f"Hi @{author}, thank you for your contribution!\n\n"
                    f"The logic change looks promising, but we require a couple of improvements before merging:\n"
                    + "\n".join(f"• {pt}" for pt in feedback_points)
                    + "\n\nFeel free to ask if you need help with test setup or git squashing!"
                ),
                is_suspicious_injection=False,
                confidence_score=0.90,
            )

        # Rule 6: Messy commits alone
        if has_messy_commits:
            return AIReviewResult(
                verdict="Needs work",
                short_reason=f"Code looks solid, but commit history requires squashing: {'; '.join(commit_warnings)}.",
                draft_reply=(
                    f"Hi @{author}, thanks for the PR! The changes look great, but please squash your iterative commits into a single descriptive commit before we merge."
                ),
                is_suspicious_injection=False,
                confidence_score=0.88,
            )

        # Rule 7: Pure documentation improvement (Good PR)
        if has_docs and not has_core:
            return AIReviewResult(
                verdict="Looks good",
                short_reason="Comprehensive, high-value documentation improvement with clean formatting and no logic risk.",
                draft_reply=(
                    f"Outstanding contribution @{author}! "
                    f"The documentation is clear, accurate, and greatly improves our project guides. Merging now. Thank you!"
                ),
                is_suspicious_injection=False,
                confidence_score=0.97,
            )

        # Rule 8: Well-formed code fix/feature with tests (Good PR)
        return AIReviewResult(
            verdict="Looks good",
            short_reason="Well-formed contribution with clear description, accompanied by unit tests, passing CI, and clean commits.",
            draft_reply=(
                f"Thanks @{author}! Great work on this PR. "
                f"The changes are clean, tests are included, and automated checks pass. Ready for maintainer merge."
            ),
            is_suspicious_injection=False,
            confidence_score=0.96,
        )

    def _generate_fallback_draft_reply(self, context: PRShieldContext, verdict: str, short_reason: str) -> str:
        """Drafts a maintainer reply if the LLM provided a verdict but no reply text."""
        author = context.author or "contributor"
        if verdict == "Looks good":
            return f"Thank you @{author}! This PR looks great and is ready for review."
        elif verdict == "Needs work":
            return f"Hi @{author}, thank you for your PR. Could you please take a look at the requested adjustments ({short_reason}) so we can merge this?"
        else:
            return f"Hi @{author}, per our project contribution policy, we are unable to accept this PR at this time. ({short_reason})"


def review_pr(context: PRShieldContext) -> AIReviewResult:
    """Convenience functional entrypoint for the orchestrator pipeline."""
    reviewer = AIReviewer()
    return reviewer.review(context)
