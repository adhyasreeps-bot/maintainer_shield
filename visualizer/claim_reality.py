"""
visualizer/claim_reality.py - Claim vs. Reality Discrepancy Comparator
Member 2 Deliverable: Highlights differences between PR claimed scope and actual touched files.
"""

import re
from typing import Dict, List, Any
from core.schemas import FileChange, categorize_file


def extract_claims(title: str, description: str) -> List[str]:
    """Extracts claimed categories from PR title and description."""
    text = f"{title.lower()} {description.lower()}"
    claimed_categories = set()

    # Explicit doc indicators
    is_doc_claim = any(
        re.search(r"\b" + re.escape(kw) + r"\b", text)
        for kw in ["doc", "docs", "documentation", "readme", "typo", "spelling", "guide", "tutorial", "markdown", "changelog"]
    )
    if is_doc_claim or re.match(r"^(docs|doc)(\(.*\))?:", title.lower()):
        claimed_categories.add("docs")

    # Explicit test indicators
    is_test_claim = any(
        re.search(r"\b" + re.escape(kw) + r"\b", text)
        for kw in ["test", "tests", "unit test", "spec", "coverage", "mock", "fixture"]
    )
    if is_test_claim or re.match(r"^(test|tests)(\(.*\))?:", title.lower()):
        claimed_categories.add("tests")

    # Explicit config indicators
    is_config_claim = any(
        re.search(r"\b" + re.escape(kw) + r"\b", text)
        for kw in ["config", "ci", "workflow", "docker", "dockerfile", "dependency", "dependencies", "bump", "package.json", "requirements"]
    )
    if is_config_claim or re.match(r"^(chore|ci|build)(\(.*\))?:", title.lower()):
        claimed_categories.add("config")

    # Explicit core indicators
    core_keywords = [
        "feature", "feat", "refactor", "auth", "token", "api", "database",
        "db", "logic", "perf", "performance", "security", "jwt", "endpoint",
        "handler", "service", "driver"
    ]
    is_core_claim = any(
        re.search(r"\b" + re.escape(kw) + r"\b", text)
        for kw in core_keywords
    )
    if is_core_claim or (re.match(r"^(feat|refactor|perf)(\(.*\))?:", title.lower()) and not is_doc_claim):
        claimed_categories.add("core")

    # If generic "fix:" or generic text without doc/test/config keywords, treat as core
    if not claimed_categories:
        claimed_categories.add("core")

    return list(claimed_categories)


def analyze_claim_vs_reality(
    title: str,
    description: str,
    files: List[FileChange]
) -> Dict[str, Any]:
    """
    Compares claimed categories against touched files and directory locations.
    Flags mismatches (e.g. claims docs typo, touches core auth logic).
    """
    claimed = extract_claims(title, description)

    actual_counts: Dict[str, int] = {}
    core_files_touched = []

    for f in files:
        cat = f.category if f.category and f.category != "other" else categorize_file(f.filename)
        actual_counts[cat] = actual_counts.get(cat, 0) + 1
        if cat == "core":
            core_files_touched.append(f.filename)

    dominant_actual = max(actual_counts, key=actual_counts.get) if actual_counts else "none"

    is_mismatch = False
    severity = "none"
    reasons = []

    # High severity: Claims docs or typo, but touches core application logic
    if "docs" in claimed and "core" not in claimed and actual_counts.get("core", 0) > 0:
        is_mismatch = True
        severity = "high"
        reasons.append(
            f"Title/description claims documentation edits, but modified {len(core_files_touched)} "
            f"core source file(s): {', '.join(core_files_touched[:3])}"
        )

    # Medium severity: Claims tests, but touches only core files without adding tests
    elif "tests" in claimed and actual_counts.get("tests", 0) == 0 and actual_counts.get("core", 0) > 0:
        is_mismatch = True
        severity = "medium"
        reasons.append("PR description mentions tests, but zero test files were added or updated.")

    # Low severity: General mismatch in dominant category
    elif dominant_actual not in claimed and len(files) > 0:
        is_mismatch = True
        severity = "low"
        reasons.append(
            f"Claimed focus is {', '.join(claimed).upper()}, but majority of changes are in {dominant_actual.upper()}."
        )

    return {
        "claimed": ", ".join(claimed),
        "actual": dominant_actual,
        "is_mismatch": is_mismatch,
        "severity": severity,
        "badge_color": "#EF4444" if severity == "high" else ("#F59E0B" if severity == "medium" else "#10B981"),
        "explanation": " ".join(reasons) if reasons else "Claimed intent matches touched files.",
        "actual_breakdown": actual_counts,
        "core_files_flagged": core_files_touched,
    }
