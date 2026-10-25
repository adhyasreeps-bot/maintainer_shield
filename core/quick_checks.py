"""
Stage 1: Quick Checks Engine for Maintainer Shield.
Performs instant, rule-based sanity checks on incoming PRs before invoking visualizers
or LLMs. Identifies empty descriptions, missing issue links, trivial whitespace/typo edits,
and failing CI statuses.
"""

import re
import difflib
from typing import List, Optional
from core.schemas import QuickCheckResults, FileChange


class QuickChecksEngine:
    """Evaluates rule-based heuristic checks on PR metadata and diffs."""

    # Common issue linking keywords recognized by GitHub
    ISSUE_LINK_PATTERNS = [
        re.compile(r"(?:close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)\s+#(\d+)", re.IGNORECASE),
        re.compile(r"(?:close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)\s+https?://[^\s]+/issues/(\d+)", re.IGNORECASE),
        re.compile(r"(?:issue|ref|refs|part of)\s+#(\d+)", re.IGNORECASE),
        re.compile(r"github\.com/[^/\s]+/[^/\s]+/issues/(\d+)", re.IGNORECASE),
        re.compile(r"#(\d+)", re.IGNORECASE),
    ]

    # Common placeholder descriptions used in low-effort PRs
    PLACEHOLDER_WORDS = {
        "asdf", "test", "testing", "update", "updates", "updated", "fix", "fixes", "fixed",
        "patch", "clean", "cleanup", "temp", "wip", "none", "nothing", "see title",
        "done", "change", "changes", "hello", "hacktoberfest", "pr"
    }

    # Template artifacts that indicate unedited template text
    TEMPLATE_MARKERS = [
        "<!-- Describe your changes here -->",
        "<!-- What does this PR do? -->",
        "<!-- Fixes # -->",
        "[ ] Describe your changes",
    ]

    @classmethod
    def check_description(cls, description: Optional[str]) -> tuple[bool, int, List[str]]:
        """Checks if description is present, non-empty, and substantive."""
        flags: List[str] = []
        if not description:
            return False, 0, ["MISSING_DESCRIPTION"]

        cleaned = description.strip()
        length = len(cleaned)

        if length == 0:
            return False, 0, ["EMPTY_DESCRIPTION"]

        # Check for unedited template comments
        for marker in cls.TEMPLATE_MARKERS:
            if marker.lower() in cleaned.lower():
                flags.append("UNEDITED_TEMPLATE")
                break

        # Check for single generic placeholder words
        clean_words = cleaned.lower().split()
        if len(clean_words) <= 2 and clean_words[0] in cls.PLACEHOLDER_WORDS:
            flags.append("PLACEHOLDER_DESCRIPTION")
        elif length < 15 and not flags:
            flags.append("DESCRIPTION_TOO_SHORT")

        has_valid_desc = not any(f in flags for f in ["MISSING_DESCRIPTION", "EMPTY_DESCRIPTION", "PLACEHOLDER_DESCRIPTION"])
        return has_valid_desc, length, flags

    @classmethod
    def extract_issue_links(cls, text: str) -> List[str]:
        """Extracts linked issue numbers or URLs from PR text."""
        if not text:
            return []
        found_issues = set()
        for pattern in cls.ISSUE_LINK_PATTERNS:
            matches = pattern.findall(text)
            for m in matches:
                found_issues.add(f"#{m}")
        return sorted(list(found_issues))

    @staticmethod
    def is_diff_whitespace_only(patch: Optional[str]) -> bool:
        """Determines if a diff patch contains only whitespace/newline changes."""
        if not patch:
            return False

        lines = patch.splitlines()
        added_lines = []
        removed_lines = []

        for line in lines:
            if line.startswith("+") and not line.startswith("+++"):
                added_lines.append(line[1:])
            elif line.startswith("-") and not line.startswith("---"):
                removed_lines.append(line[1:])

        if not added_lines and not removed_lines:
            return False

        # If stripping all whitespace from added equals stripping all whitespace from removed
        added_clean = "".join("".join(added_lines).split())
        removed_clean = "".join("".join(removed_lines).split())

        return added_clean == removed_clean

    @classmethod
    def check_diff_triviality(cls, files: List[FileChange]) -> tuple[bool, List[str]]:
        """Checks if the PR is a trivial whitespace-only or single-character typo edit."""
        flags: List[str] = []
        if not files:
            return False, ["ZERO_FILES_CHANGED"]

        total_additions = sum(f.additions for f in files)
        total_deletions = sum(f.deletions for f in files)

        # Check for whitespace-only diffs across all files
        all_patches = [f.patch for f in files if f.patch]
        if all_patches and all(cls.is_diff_whitespace_only(p) for p in all_patches):
            flags.append("WHITESPACE_ONLY_DIFF")
            return True, flags

        # Check for 1-character or single-word typo edit in doc file
        if len(files) == 1 and files[0].category == "docs" and total_additions <= 2 and total_deletions <= 2:
            patch = files[0].patch or ""
            # Check ratio of similarity
            added = [l[1:] for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++")]
            removed = [l[1:] for l in patch.splitlines() if l.startswith("-") and not l.startswith("---")]
            if added and removed:
                sim = difflib.SequenceMatcher(None, "".join(added), "".join(removed)).ratio()
                if sim > 0.85:
                    flags.append("TRIVIAL_TYPO_DIFF")
                    return True, flags

        return False, flags

    @classmethod
    def evaluate(
        cls,
        title: str,
        description: Optional[str],
        files: List[FileChange],
        ci_status: str = "none",
    ) -> QuickCheckResults:
        """Runs the complete suite of Stage 1 Quick Checks."""
        flags: List[str] = []
        full_text = f"{title}\n{description or ''}"

        # 1. Description checks
        has_desc, desc_len, desc_flags = cls.check_description(description)
        flags.extend(desc_flags)

        # 2. Issue link checks
        linked_issues = cls.extract_issue_links(full_text)
        has_issue = len(linked_issues) > 0
        if not has_issue:
            flags.append("NO_ISSUE_LINK")

        # 3. Diff triviality / whitespace checks
        is_trivial, diff_flags = cls.check_diff_triviality(files)
        flags.extend(diff_flags)

        # 4. CI checks
        normalized_ci = ci_status.lower() if ci_status in ["passed", "failed", "pending", "none"] else "none"
        if normalized_ci == "failed":
            flags.append("CI_TESTS_FAILING")
        elif normalized_ci == "pending":
            flags.append("CI_TESTS_PENDING")

        # 5. Check if core code was modified without any tests
        has_core_changes = any(f.category == "core" for f in files)
        has_test_changes = any(f.category == "tests" for f in files)
        if has_core_changes and not has_test_changes:
            flags.append("NO_TESTS_INCLUDED")

        # Heuristic scoring (Starts at 100)
        score = 100
        penalties = {
            "MISSING_DESCRIPTION": 30,
            "EMPTY_DESCRIPTION": 30,
            "PLACEHOLDER_DESCRIPTION": 25,
            "UNEDITED_TEMPLATE": 20,
            "DESCRIPTION_TOO_SHORT": 10,
            "NO_ISSUE_LINK": 15,
            "WHITESPACE_ONLY_DIFF": 40,
            "TRIVIAL_TYPO_DIFF": 30,
            "CI_TESTS_FAILING": 35,
            "NO_TESTS_INCLUDED": 20,
            "ZERO_FILES_CHANGED": 50,
        }
        for flag in flags:
            score -= penalties.get(flag, 5)
        score = max(0, min(100, score))

        # Generate human-readable summary
        summary_parts = []
        if not has_desc:
            summary_parts.append("Missing/empty description")
        if not has_issue:
            summary_parts.append("No linked issue")
        if is_trivial:
            summary_parts.append("Trivial or whitespace-only diff")
        if normalized_ci == "failed":
            summary_parts.append("Failing CI test suite")
        if has_core_changes and not has_test_changes:
            summary_parts.append("Core logic modified without tests")

        summary = "; ".join(summary_parts) if summary_parts else "Quick checks passed with no major flags."

        return QuickCheckResults(
            has_description=has_desc,
            description_length=desc_len,
            has_issue_link=has_issue,
            linked_issues=linked_issues,
            is_whitespace_or_typo_only=is_trivial,
            ci_status=normalized_ci,  # type: ignore
            flags=flags,
            score=score,
            summary=summary,
        )


def run_quick_checks(
    title: str,
    description: Optional[str],
    files: List[FileChange],
    ci_status: str = "none"
) -> QuickCheckResults:
    """Convenience functional wrapper for QuickChecksEngine.evaluate."""
    return QuickChecksEngine.evaluate(title, description, files, ci_status)
