"""
ai/__init__.py - Maintainer Shield AI & Security Package
Member 3 Deliverable: Local AI Reviewer, Prompt Security & Evaluation/Demo Lead.

Exports:
- AIReviewer: Orchestrates Stage 3 & 4 AI Review and Tone Tuning
- OllamaClient: Local LLM integration with structured JSON validation
- InjectionDetector: Defenses against adversarial prompt injections and breakouts
- InjectionScanResult: Security scan report schema
- review_pr: Pipeline hook for orchestrator
"""

from ai.injection_detector import InjectionDetector, InjectionScanResult
from ai.prompts import SYSTEM_PROMPT, build_review_prompt
from ai.ollama_client import OllamaClient
from ai.reviewer import AIReviewer, review_pr

__all__ = [
    "AIReviewer",
    "OllamaClient",
    "InjectionDetector",
    "InjectionScanResult",
    "SYSTEM_PROMPT",
    "build_review_prompt",
    "review_pr",
]
