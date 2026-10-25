"""
Shared Data Contracts & Schemas for Maintainer Shield.
Defined collaboratively for integration between:
- Member 1: Backend, Ingestion & Quick Checks
- Member 2: Visualizer Engine & Dashboard
- Member 3: Ollama AI Review & Security Guardrails
"""

import os
from typing import List, Optional, Dict, Literal, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field


FileCategory = Literal["core", "tests", "docs", "config", "other"]


def categorize_file(filename: str) -> FileCategory:
    """Categorizes a file based on path conventions and file extensions.

    - tests: test files, spec files, test suites
    - docs: markdown, rst, documentation directories
    - config: package manifests, github workflows, dockerfiles, lockfiles
    - core: source code files
    - other: static assets, images, etc.
    """
    path_lower = filename.lower().replace("\\", "/")
    basename = os.path.basename(path_lower)
    _, ext = os.path.splitext(path_lower)

    # Tests check
    if any(pattern in path_lower for pattern in ["/test/", "/tests/", "test_", "_test.", ".spec.", ".test."]):
        return "tests"

    # Docs check
    if any(path_lower.startswith(d) for d in ["docs/", "doc/"]) or ext in [".md", ".rst", ".txt", ".adoc"]:
        return "docs"

    # Config & Build check
    config_basenames = [
        "dockerfile", "makefile", "license", ".gitignore", ".env.example",
        "package.json", "package-lock.json", "tsconfig.json",
        "pyproject.toml", "requirements.txt", "setup.py", "setup.cfg",
        "cargo.toml", "cargo.lock", "go.mod", "go.sum", "pom.xml"
    ]
    if (
        basename in config_basenames
        or path_lower.startswith(".github/")
        or ext in [".yaml", ".yml", ".toml", ".ini", ".cfg"]
    ):
        return "config"

    # Code / Core check
    code_extensions = [
        ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".c", ".cpp", ".h",
        ".rs", ".go", ".rb", ".php", ".cs", ".swift", ".kt", ".scala", ".sql", ".sh"
    ]
    if ext in code_extensions or any(path_lower.startswith(d) for d in ["src/", "lib/", "app/", "core/"]):
        return "core"

    return "other"


class FileChange(BaseModel):
    """Represents a single file touched in a Pull Request."""
    filename: str
    category: FileCategory = "other"
    additions: int = 0
    deletions: int = 0
    status: str = "modified"  # added, modified, removed, renamed
    patch: Optional[str] = None
    raw_url: Optional[str] = None


class QuickCheckResults(BaseModel):
    """Stage 1: Rule-based fast sanity check results."""
    has_description: bool
    description_length: int
    has_issue_link: bool
    linked_issues: List[str] = Field(default_factory=list)
    is_whitespace_or_typo_only: bool
    ci_status: Literal["passed", "failed", "pending", "none"]
    flags: List[str] = Field(default_factory=list)
    score: int = Field(default=100, description="Heuristic score from 0 to 100")
    summary: str = ""


class VisualizerData(BaseModel):
    """Stage 2: Change visualizer & diagram representations."""
    mermaid_diagram: str = ""
    treemap_nodes: List[Dict[str, Any]] = Field(default_factory=list)
    claim_vs_reality: Dict[str, Any] = Field(default_factory=dict)
    commit_pattern_warnings: List[str] = Field(default_factory=list)


class AIReviewResult(BaseModel):
    """Stage 3 & 4: Ollama Local AI review output & verdict."""
    verdict: Literal["Looks good", "Needs work", "Likely junk"]
    short_reason: str
    draft_reply: str
    is_suspicious_injection: bool = False
    confidence_score: float = 1.0


class PRShieldContext(BaseModel):
    """Complete context for an analyzed PR across all 4 stages."""
    pr_id: int
    pr_url: str
    repo_name: str
    author: str
    title: str
    raw_description: str
    head_branch: str = "main"
    base_branch: str = "main"
    commits: List[Dict[str, Any]] = Field(default_factory=list)
    files: List[FileChange] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    quick_checks: Optional[QuickCheckResults] = None
    visualization: Optional[VisualizerData] = None
    ai_review: Optional[AIReviewResult] = None
    maintainer_decision: Optional[str] = None
    maintainer_custom_reply: Optional[str] = None
