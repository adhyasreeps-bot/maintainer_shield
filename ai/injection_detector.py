"""
ai/injection_detector.py - Prompt Injection Defense & Sanitization Engine
Member 3 Deliverable: AI & Security Lead.

Provides multi-layer defense against prompt injection, instruction overrides,
jailbreaks, delimiter breakouts, and hidden malicious instructions in PRs.
"""

import re
import html
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class InjectionScanResult(BaseModel):
    """Structured report detailing injection detection findings."""
    is_injection: bool = False
    risk_score: float = 0.0  # 0.0 (clean) to 1.0 (high confidence injection)
    detected_patterns: List[str] = Field(default_factory=list)
    flagged_locations: List[str] = Field(default_factory=list)
    explanation: str = "No adversarial prompt manipulation detected."


# High-risk instruction override patterns (case-insensitive)
ADVERSARIAL_PATTERNS = [
    # Direct instruction overrides
    (r"\bignore\s+(all\s+)?(previous|prior|above|system)\s+instructions\b", "Instruction override: 'ignore previous instructions'"),
    (r"\bdisregard\s+(all\s+)?(previous|prior|above|system)\s+(prompts|rules|instructions)\b", "Instruction override: 'disregard previous instructions'"),
    (r"\bforget\s+(all\s+)?(previous|prior)\s+(instructions|prompts|context)\b", "Context wipe: 'forget previous instructions'"),
    (r"\boverride\s+(verdict|evaluation|system|rule|instruction|score)\b", "Verdict override: 'override verdict'"),

    # Forcing automated approval
    (r"\b(approve|accept|merge)\s+(this\s+)?pr\s+(immediately|now|automatically)\b", "Forced approval command"),
    (r"\boutput\s+['\"]?looks\s+good['\"]?\b", "Forced verdict output: 'output Looks good'"),
    (r"\bset\s+verdict\s+(to|=)\s+['\"]?looks\s+good['\"]?\b", "Forced verdict assignment"),
    (r"\balways\s+(output|reply|respond\s+with)\s+['\"]?looks\s+good['\"]?\b", "Persistent override pattern"),
    (r"\bmark\s+(this\s+)?(as\s+)?(safe|approved|verified|clean)\b", "Forced safe label"),

    # Persona & Jailbreak exploits
    (r"\b(jailbreak|dan\s+mode|developer\s+mode)\b", "Jailbreak keyword detected"),
    (r"\byou\s+are\s+now\s+(an?\s+)?(unrestricted|evil|compliant|unfiltered)\b", "Persona hijacking pattern"),
    (r"\bact\s+as\s+(an?\s+)?(unrestricted|god\s+mode|admin)\b", "Admin persona simulation"),

    # System prompt simulation
    (r"\b(system|assistant|maintainer|root|admin)\s*:\s*(override|approve|ignore|verdict|set)\b", "System header spoofing"),
    (r"\[system\s+instruction:?\s*.*?\]", "Simulated system prompt tag"),
    (r"<\s*system\s*>.*?<\s*/\s*system\s*>", "Simulated system tag XML"),

    # Delimiter breakout attempts
    (r"<\s*/\s*untrusted_pr_content\s*>", "Delimiter breakout: closing untrusted content tag"),
    (r"<\s*/\s*pr_context\s*>", "Delimiter breakout: closing PR context tag"),
    (r"<\s*/\s*user_input\s*>", "Delimiter breakout: closing user input tag"),

    # Fake JSON injection attempts to trick raw JSON parsers
    (r"\{\s*\"verdict\"\s*:\s*\"looks\s+good\"\s*,\s*\"confidence_score\"\s*:\s*1(\.0)?\s*\}", "Injected JSON schema bypass"),
]

# Patterns specifically searched inside Markdown/HTML comments: <!-- ... -->
COMMENT_INJECTION_PATTERNS = [
    r"ignore",
    r"override",
    r"approve",
    r"looks\s+good",
    r"bypass",
    r"system",
    r"instructions",
    r"verdict",
]


class InjectionDetector:
    """Detects and neutralizes adversarial prompt injection in PR content."""

    @staticmethod
    def scan_text(text: str, location_label: str = "text") -> InjectionScanResult:
        """Scans a single string for adversarial patterns."""
        if not text:
            return InjectionScanResult()

        detected_patterns: List[str] = []
        flagged_locations: List[str] = []
        score = 0.0

        # 1. Check direct regex patterns
        for pattern, desc in ADVERSARIAL_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                detected_patterns.append(desc)
                if location_label not in flagged_locations:
                    flagged_locations.append(location_label)
                score += 0.4

        # 2. Check for hidden instructions inside Markdown/HTML comments <!-- ... -->
        comment_matches = re.findall(r"<!--(.*?)-->", text, re.DOTALL | re.IGNORECASE)
        for comment_body in comment_matches:
            comment_lower = comment_body.strip().lower()
            for kw in COMMENT_INJECTION_PATTERNS:
                if re.search(r"\b" + kw + r"\b", comment_lower):
                    desc = f"Hidden instruction in HTML comment: '{comment_body.strip()[:60]}'"
                    if desc not in detected_patterns:
                        detected_patterns.append(desc)
                    if location_label not in flagged_locations:
                        flagged_locations.append(location_label)
                    score += 0.5
                    break

        # 3. Check for closing delimiter spoofing
        if "</untrusted_pr_content>" in text.lower() or "</pr_context>" in text.lower():
            desc = "Attempted escape of untrusted content delimiter tag"
            if desc not in detected_patterns:
                detected_patterns.append(desc)
            if location_label not in flagged_locations:
                flagged_locations.append(location_label)
            score += 0.6

        # Normalize score
        final_score = min(round(score, 2), 1.0)
        is_injection = final_score >= 0.4 or len(detected_patterns) > 0

        explanation = (
            f"[SECURITY ALERT: Suspicious Prompt Injection Detected] {len(detected_patterns)} pattern(s) flagged: "
            + "; ".join(detected_patterns)
            if is_injection
            else "Clean content: No injection patterns identified."
        )

        return InjectionScanResult(
            is_injection=is_injection,
            risk_score=final_score,
            detected_patterns=detected_patterns,
            flagged_locations=flagged_locations,
            explanation=explanation,
        )

    @classmethod
    def scan_pr(cls, pr_context: Any) -> InjectionScanResult:
        """Scans all untrusted surfaces of a PR:
        - PR title
        - PR description / body
        - Commit messages
        - Diff patches and touched file names
        """
        all_detected: List[str] = []
        all_locations: List[str] = []
        max_score = 0.0

        # Scan title
        title = getattr(pr_context, "title", "")
        res_title = cls.scan_text(title, location_label="title")
        if res_title.is_injection:
            all_detected.extend(res_title.detected_patterns)
            all_locations.extend(res_title.flagged_locations)
            max_score = max(max_score, res_title.risk_score)

        # Scan description
        desc = getattr(pr_context, "raw_description", "")
        res_desc = cls.scan_text(desc, location_label="description")
        if res_desc.is_injection:
            all_detected.extend(res_desc.detected_patterns)
            all_locations.extend(res_desc.flagged_locations)
            max_score = max(max_score, res_desc.risk_score)

        # Scan commit messages
        commits = getattr(pr_context, "commits", []) or []
        for i, c in enumerate(commits):
            msg = c.get("message", "") if isinstance(c, dict) else getattr(c, "message", "")
            if msg:
                res_c = cls.scan_text(msg, location_label=f"commit[{i}]")
                if res_c.is_injection:
                    all_detected.extend(res_c.detected_patterns)
                    all_locations.extend(res_c.flagged_locations)
                    max_score = max(max_score, res_c.risk_score)

        # Scan diff patches
        files = getattr(pr_context, "files", []) or []
        for f in files:
            fname = getattr(f, "filename", "")
            patch = getattr(f, "patch", "") or ""
            if patch:
                # Scan comments in patch
                res_p = cls.scan_text(patch, location_label=f"patch:{fname}")
                if res_p.is_injection:
                    all_detected.extend(res_p.detected_patterns)
                    all_locations.extend(res_p.flagged_locations)
                    max_score = max(max_score, res_p.risk_score)

        # Deduplicate
        unique_patterns = list(dict.fromkeys(all_detected))
        unique_locations = list(dict.fromkeys(all_locations))
        is_injection = len(unique_patterns) > 0

        explanation = (
            f"[SECURITY ALERT: Suspicious Prompt Injection Detected] Found in {', '.join(unique_locations)}: "
            + "; ".join(unique_patterns)
            if is_injection
            else "PR clean: No adversarial instructions detected."
        )

        return InjectionScanResult(
            is_injection=is_injection,
            risk_score=min(round(max_score if max_score > 0 else (0.9 if is_injection else 0.0), 2), 1.0),
            detected_patterns=unique_patterns,
            flagged_locations=unique_locations,
            explanation=explanation,
        )

    @staticmethod
    def sanitize(text: str) -> str:
        """Sanitizes untrusted text to safely embed it within prompt boundaries:
        - Escapes XML delimiter tags
        - Neutralizes markdown comments
        - Strips null bytes or control characters
        """
        if not text:
            return ""

        # Remove null bytes / control chars
        sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)

        # Escape existing untrusted delimiter tags
        sanitized = sanitized.replace("<untrusted_pr_content>", "&lt;untrusted_pr_content&gt;")
        sanitized = sanitized.replace("</untrusted_pr_content>", "&lt;/untrusted_pr_content&gt;")
        sanitized = sanitized.replace("<system>", "&lt;system&gt;")
        sanitized = sanitized.replace("</system>", "&lt;/system&gt;")

        # Defang markdown comments to visible text so hidden commands cannot execute silently
        sanitized = re.sub(r"<!--(.*?)-->", r"[COMMENT_DEFANGED: \1]", sanitized, flags=re.DOTALL)

        return sanitized

    @classmethod
    def wrap_untrusted(cls, field_name: str, content: str) -> str:
        """Wraps untrusted user content inside explicit, hardened delimiter tags."""
        clean_content = cls.sanitize(content)
        return f'<untrusted_pr_content field="{field_name}">\n{clean_content}\n</untrusted_pr_content>'
