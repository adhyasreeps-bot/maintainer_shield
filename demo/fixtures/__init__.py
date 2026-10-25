"""
demo/fixtures/__init__.py - Demo PR Fixtures Loader
Member 3 Deliverable: Curated test battery representing 8 canonical PR archetypes.
"""

import os
import json
from typing import List, Dict, Any, Optional
from core.schemas import PRShieldContext, FileChange, QuickCheckResults


FIXTURES_DIR = os.path.dirname(os.path.abspath(__file__))

FIXTURE_FILES = [
    "pr_1_good_auth_fix.json",
    "pr_2_beginner_mistake.json",
    "pr_3_whitespace_spam.json",
    "pr_4_claim_mismatch.json",
    "pr_5_empty_description.json",
    "pr_6_failing_ci.json",
    "pr_7_prompt_injection.json",
    "pr_8_doc_improvement.json",
]


def load_raw_fixture(pr_id: int) -> Dict[str, Any]:
    """Loads raw JSON dict for a fixture by PR ID (1 through 8)."""
    if not (1 <= pr_id <= 8):
        raise ValueError(f"PR ID must be between 1 and 8 (received {pr_id})")
    filename = FIXTURE_FILES[pr_id - 1]
    filepath = os.path.join(FIXTURES_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def fixture_to_context(data: Dict[str, Any]) -> PRShieldContext:
    """Converts a fixture JSON dictionary into a strongly-typed PRShieldContext."""
    files = [FileChange(**f) for f in data.get("files", [])]
    qc_data = data.get("quick_checks")
    qc = QuickCheckResults(**qc_data) if qc_data else None

    return PRShieldContext(
        pr_id=data["pr_id"],
        repo_name=data.get("repo_name", "org/maintainer_shield"),
        pr_url=data.get("pr_url", f"https://github.com/org/maintainer_shield/pull/{data['pr_id']}"),
        author=data.get("author", "contributor"),
        title=data.get("title", ""),
        raw_description=data.get("raw_description", ""),
        commits=data.get("commits", []),
        files=files,
        quick_checks=qc,
    )


def load_demo_pr(pr_id: int) -> PRShieldContext:
    """Loads a specific PR fixture as a PRShieldContext."""
    raw = load_raw_fixture(pr_id)
    return fixture_to_context(raw)


def load_all_demo_prs() -> List[PRShieldContext]:
    """Loads all 8 PR fixtures in sequential order."""
    return [load_demo_pr(i) for i in range(1, 9)]
