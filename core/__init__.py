"""
Maintainer Shield: Core Package
Provides GitHub integration, Stage 1 Quick Checks, local database persistence,
and the pipeline orchestrator.
"""

from core.schemas import (
    FileCategory,
    FileChange,
    QuickCheckResults,
    VisualizerData,
    AIReviewResult,
    PRShieldContext,
    categorize_file,
)
from core.github_client import GitHubClient
from core.quick_checks import QuickChecksEngine, run_quick_checks
from core.db import ShieldDatabase
from core.orchestrator import ShieldOrchestrator

__all__ = [
    "FileCategory",
    "FileChange",
    "QuickCheckResults",
    "VisualizerData",
    "AIReviewResult",
    "PRShieldContext",
    "categorize_file",
    "GitHubClient",
    "QuickChecksEngine",
    "run_quick_checks",
    "ShieldDatabase",
    "ShieldOrchestrator",
]
