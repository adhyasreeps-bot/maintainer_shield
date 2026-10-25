"""
visualizer/commit_graph.py - Commit Topology and Pattern Detector
Member 2 Deliverable: Flags messy commit hygiene and provides squash recommendations.
"""

import re
from typing import Dict, List, Tuple, Any

SUSPICIOUS_COMMIT_PATTERNS = [
    r"^(fix|fixed|fixes)\s*\d*$",
    r"^(update|updated|updates)\s*\d*$",
    r"^(test|tests|testing)\s*\d*$",
    r"^(asdf|wip|temp|tmp|foo|bar|baz)$",
    r"^(changes|cleanup|minor|edit|done)$",
    r"^\.$",
]


def detect_commit_patterns(commits: List[Dict[str, Any]]) -> Tuple[List[str], bool]:
    """
    Analyzes commit history for anti-patterns and generates squash recommendations.
    Returns (warnings, squash_recommended).
    """
    warnings = []
    squash_recommended = False
    flagged_messages = []

    if not commits:
        return ["No commit history provided."], False

    for c in commits:
        msg = c.get("message", "").strip().lower()
        sha = str(c.get("sha", "0000000"))[:7]

        # Check regex anti-patterns
        for pattern in SUSPICIOUS_COMMIT_PATTERNS:
            if re.match(pattern, msg):
                flagged_messages.append((sha, c.get("message", "")))
                break

    # If 2 or more iterative / low-effort commits are detected
    if len(flagged_messages) >= 2:
        squash_recommended = True
        examples = ", ".join([f"'{m[1]}' ({m[0]})" for m in flagged_messages[:3]])
        warnings.append(
            f"Found {len(flagged_messages)} non-descriptive / iterative commits ({examples}). "
            f"Squash recommendation: suggest squashing into a single atomic commit before merging."
        )
    elif len(flagged_messages) == 1:
        warnings.append(f"Commit '{flagged_messages[0][1]}' is non-descriptive.")

    # High commit count warning for small PRs
    if len(commits) > 6:
        squash_recommended = True
        warnings.append(f"PR contains {len(commits)} commits. Consider requesting a branch rebase & squash.")

    return warnings, squash_recommended


def generate_commit_timeline(commits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generates structured timeline data with status badges for dashboard rendering."""
    timeline = []
    for c in commits:
        msg = c.get("message", "").strip()
        sha = str(c.get("sha", "0000000"))[:7]
        author = c.get("author", "contributor")

        is_flagged = any(re.match(pat, msg.lower()) for pat in SUSPICIOUS_COMMIT_PATTERNS)

        timeline.append({
            "sha": sha,
            "message": msg,
            "author": author,
            "is_flagged": is_flagged,
            "status_badge": "⚠️ Needs Squash" if is_flagged else "✅ Clean",
        })
    return timeline
