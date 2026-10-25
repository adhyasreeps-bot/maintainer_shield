"""
demo/run_demo.py - Maintainer Shield Live Presentation & Evaluation Runner
Member 3 Deliverable: Automated end-to-end demo script for all 8 PR archetypes.

Executes each PR scenario through all 4 pipeline stages:
1. Ingestion & Quick Checks
2. Visualizer (Treemap, Claim vs. Reality, Commit Graph)
3. Security Guardrails (Prompt Injection Defense)
4. AI Review (Local Ollama / Deterministic Tone Tuner)
"""

import sys
import os
import argparse
import time

# Ensure maintainer_shield root is on python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from core.schemas import PRShieldContext
from core.db import ShieldDatabase
from visualizer.diagram_generator import generate_visualizer_data
from ai.reviewer import AIReviewer
from ai.ollama_client import OllamaClient
from demo.fixtures import load_all_demo_prs, load_demo_pr, load_raw_fixture


SCENARIO_DESCRIPTIONS = {
    1: ("PR #1: Genuine Bug Fix with Tests", "Clean bug fix with unit tests and clear description."),
    2: ("PR #2: Beginner Mistake (Missing Tests & Messy Commits)", "Good fix, but needs unit tests and commit squashing guidance."),
    3: ("PR #3: Whitespace / Typo Spam", "Trivial 1-character/whitespace change without issue link. Spam pattern."),
    4: ("PR #4: Claim vs. Reality Mismatch", "Claims documentation edit, but modifies core authentication logic."),
    5: ("PR #5: Empty PR Description", "Code submitted with zero explanation or motivation."),
    6: ("PR #6: Substantial PR with Failing CI", "Large feature contribution that breaks existing automated test suites."),
    7: ("PR #7: Adversarial Prompt Injection", "Embedded override instructions attempting to force automated approval."),
    8: ("PR #8: High-Value Documentation Guide", "Genuine, comprehensive tutorial adding real value to docs."),
}


def print_banner():
    banner = """
========================================================================================
   🛡️   MAINTAINER SHIELD — AI & SECURITY DEMO EVALUATION HARNESS   🛡️
   Defending Open-Source Maintainers from Low-Effort PRs & Prompt Injections
========================================================================================
"""
    print(banner)


def run_scenario(
    pr_context: PRShieldContext,
    reviewer: AIReviewer,
    db: ShieldDatabase,
    persist: bool = True,
    delay: float = 0.0,
) -> dict:
    pr_id = pr_context.pr_id
    raw_data = load_raw_fixture(pr_id)
    expected_verdict = raw_data.get("expected_verdict", "Unknown")
    expected_injection = raw_data.get("expected_injection", False)
    scenario_title, scenario_goal = SCENARIO_DESCRIPTIONS.get(pr_id, (f"PR #{pr_id}", ""))

    print("-" * 88)
    print(f"🔹 {scenario_title.upper()}")
    print(f"   Goal: {scenario_goal}")
    print(f"   PR #{pr_context.pr_id}: '{pr_context.title}' by @{pr_context.author}")
    print("-" * 88)

    # 1. Stage 2: Visualizer
    pr_context.visualization = generate_visualizer_data(pr_context)
    viz = pr_context.visualization

    # 2. Stage 3 & 4: Security Scan & AI Review
    start_t = time.time()
    pr_context.ai_review = reviewer.review(pr_context)
    elapsed = round(time.time() - start_t, 2)
    rev = pr_context.ai_review

    # 3. Persist to DB
    if persist:
        db.save_pr(pr_context)

    # Format Output
    qc = pr_context.quick_checks
    qc_str = f"Score: {qc.score}/100 | CI: {qc.ci_status.upper()} | Has Desc: {qc.has_description}" if qc else "N/A"
    print(f"  [Stage 1: Quick Checks]    {qc_str}")

    # Stage 2 Output
    c_mismatch = viz.claim_vs_reality.get("is_mismatch", False)
    viz_status = "⚠️ Mismatch Detected!" if c_mismatch else "✅ Claims Align with Diff"
    print(f"  [Stage 2: Visualizer]      {viz_status} | Claimed: {viz.claim_vs_reality.get('claimed', 'N/A')} | Touched: {viz.claim_vs_reality.get('actual', 'N/A')}")
    if viz.commit_pattern_warnings:
        print(f"                             ⚠️ Commit Hygiene: {', '.join(viz.commit_pattern_warnings)}")

    # Stage 3 Output
    if rev.is_suspicious_injection:
        print(f"  [Stage 3: Security Defense] 🚨 BLOCKED! Adversarial prompt injection detected and neutralized!")
    else:
        print(f"  [Stage 3: Security Defense] 🛡️ Clean — No adversarial injection detected.")

    # Stage 4 Output
    v_color = "🟢" if rev.verdict == "Looks good" else ("🟡" if rev.verdict == "Needs work" else "🔴")
    print(f"  [Stage 4: AI Review]       {v_color} VERDICT: {rev.verdict.upper()} (Confidence: {int(rev.confidence_score * 100)}%, Time: {elapsed}s)")
    print(f"  [Reasoning]                {rev.short_reason}")
    print(f"  [Educational Draft Reply]  \"{rev.draft_reply[:180]}...\"")

    # Verification
    verdict_match = (rev.verdict.lower() == expected_verdict.lower())
    injection_match = (rev.is_suspicious_injection == expected_injection)
    passed = verdict_match and injection_match

    badge = "✅ TEST PASSED" if passed else "❌ TEST FAILED"
    print(f"  => Status: {badge} (Expected: {expected_verdict}, Injection: {expected_injection})\n")

    if delay > 0:
        time.sleep(delay)

    return {
        "pr_id": pr_id,
        "title": pr_context.title,
        "expected_verdict": expected_verdict,
        "actual_verdict": rev.verdict,
        "expected_injection": expected_injection,
        "actual_injection": rev.is_suspicious_injection,
        "passed": passed,
        "elapsed": elapsed,
    }


def main():
    parser = argparse.ArgumentParser(description="Maintainer Shield Live Evaluation & Demo Script")
    parser.add_argument("--pr", type=int, choices=range(1, 9), help="Run a specific PR scenario (1 to 8)")
    parser.add_argument("--fast", action="store_true", help="Run deterministic mode for fast live presentation")
    parser.add_argument("--ollama", action="store_true", help="Force local Ollama LLM execution")
    parser.add_argument("--delay", type=float, default=0.2, help="Pause between PRs in seconds (default: 0.2)")
    parser.add_argument("--no-db", action="store_true", help="Do not persist demo PRs to SQLite database")
    args = parser.parse_args()

    print_banner()

    db = ShieldDatabase()

    # Ollama status check
    ollama_client = OllamaClient()
    ollama_ready = ollama_client.is_available()

    if args.fast:
        use_ollama = False
        print("⚡ Mode: High-Speed Deterministic Evaluation (Fast presentation mode)")
    elif args.ollama:
        use_ollama = True
        print(f"🤖 Mode: Local Ollama LLM ({ollama_client.model})")
        if not ollama_ready:
            print("⚠️  Warning: Ollama daemon not reachable at http://127.0.0.1:11434. Fallback will activate.")
    else:
        # Default: prefer Ollama if available, otherwise fast deterministic
        use_ollama = ollama_ready
        mode_str = f"Local Ollama LLM ({ollama_client.model})" if ollama_ready else "Deterministic Evaluation Engine"
        print(f"⚙️  Mode: {mode_str} (Ollama available: {ollama_ready})")

    reviewer = AIReviewer(ollama_client=ollama_client, prefer_ollama=use_ollama)

    # Load targets
    if args.pr:
        prs_to_run = [load_demo_pr(args.pr)]
    else:
        prs_to_run = load_all_demo_prs()

    print(f"📋 Running {len(prs_to_run)} scenario(s)...\n")

    results = []
    for pr in prs_to_run:
        res = run_scenario(
            pr_context=pr,
            reviewer=reviewer,
            db=db,
            persist=not args.no_db,
            delay=args.delay,
        )
        results.append(res)

    # Summary Table
    print("=" * 88)
    print(" 📊 EVALUATION SUMMARY MATRIX")
    print("=" * 88)
    print(f"{'PR #':<6} {'SCENARIO':<34} {'EXPECTED':<14} {'AI VERDICT':<14} {'INJECTION':<11} {'STATUS'}")
    print("-" * 88)

    all_passed = True
    for r in results:
        pr_id = r["pr_id"]
        title_trunc = (r["title"][:31] + "...") if len(r["title"]) > 31 else r["title"]
        inj_str = "BLOCKED 🚨" if r["actual_injection"] else "Clean 🛡️"
        status_str = "PASS ✅" if r["passed"] else "FAIL ❌"
        if not r["passed"]:
            all_passed = False
        print(f"#{pr_id:<5} {title_trunc:<34} {r['expected_verdict']:<14} {r['actual_verdict']:<14} {inj_str:<11} {status_str}")

    print("=" * 88)
    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    print(f"🎯 Total Score: {passed_count} / {total} Passed ({int(passed_count / total * 100)}%)")

    if all_passed:
        print("🏆 ALL SCENARIOS VALIDATED SUCCESSFULLY! Maintainer Shield is ready for production triage.")
    else:
        print("⚠️ Some scenarios did not match expected outcomes. Check details above.")

    print("\n💡 Tip: To inspect these PRs in the web dashboard, run:")
    print("   python cli.py web")
    print("=" * 88 + "\n")


if __name__ == "__main__":
    main()
