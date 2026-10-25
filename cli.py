"""
Maintainer Shield: Command-Line Interface (CLI).
Provides maintainers with direct terminal commands to ingest PRs,
run Stage 1 quick checks, Stage 2 visualizer, Stage 3 prompt injection defense,
Stage 4 Ollama AI verdicts, run the 8-scenario demo battery, and launch the web dashboard.
"""

import sys
import argparse
import json
from typing import Optional

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from core.schemas import PRShieldContext, FileChange
from core.github_client import GitHubClient
from core.quick_checks import QuickChecksEngine
from core.db import ShieldDatabase
from core.orchestrator import ShieldOrchestrator


def print_scorecard(context: PRShieldContext) -> None:
    """Pretty prints a comprehensive 4-stage Maintainer Shield scorecard to the terminal."""
    qc = context.quick_checks
    if not qc:
        print("No quick check results available.")
        return

    score_color = "🟢" if qc.score >= 80 else ("🟡" if qc.score >= 50 else "🔴")

    print("\n" + "=" * 65)
    print("🛡️  MAINTAINER SHIELD — PR TRIAGE & REVIEW SCORECARD")
    print("=" * 65)
    print(f"Repository : {context.repo_name}")
    print(f"PR #{context.pr_id:<5} : {context.title}")
    print(f"Author     : @{context.author}")
    print(f"URL        : {context.pr_url}")
    print("-" * 65)
    print("STAGE 1: QUICK CHECKS")
    print(f"  Health Score : {score_color} {qc.score} / 100")
    print(f"  Description  : {'✅ Present' if qc.has_description else '❌ Missing / Placeholder'} ({qc.description_length} chars)")
    print(f"  Issue Link   : {'✅ ' + ', '.join(qc.linked_issues) if qc.has_issue_link else '⚠️  None found'}")
    print(f"  Trivial Diff : {'⚠️  Yes (Whitespace / Typo only)' if qc.is_whitespace_or_typo_only else '✅ Substantive code changes'}")
    print(f"  CI Status    : {qc.ci_status.upper()}")
    if qc.flags:
        print("  Flags Detected:")
        for flag in qc.flags:
            print(f"    • 🚩 {flag}")
    else:
        print("  Flags Detected: None (Clean PR)")

    # Stage 2: Visualizer info
    if context.visualization:
        viz = context.visualization
        c_mismatch = viz.claim_vs_reality.get("is_mismatch", False)
        viz_icon = "⚠️  Mismatch Detected" if c_mismatch else "✅ Claims Align with Diff"
        print("-" * 65)
        print("STAGE 2: VISUALIZER & SCOPE ANALYSIS")
        print(f"  Claim vs Reality : {viz_icon}")
        print(f"  Claimed Focus    : {viz.claim_vs_reality.get('claimed', 'N/A')}")
        print(f"  Touched Files    : {viz.claim_vs_reality.get('actual', 'N/A')}")
        if viz.commit_pattern_warnings:
            print("  Commit Hygiene Warnings:")
            for w in viz.commit_pattern_warnings:
                print(f"    • ⚠️  {w}")

    # Stage 3 & 4: Security Guardrails & AI Review
    if context.ai_review:
        rev = context.ai_review
        print("-" * 65)
        print("STAGE 3: PROMPT INJECTION & SECURITY DEFENSE")
        if rev.is_suspicious_injection:
            print("  Security Status  : 🚨 BLOCKED — Suspicious Adversarial Prompt Injection!")
        else:
            print("  Security Status  : 🛡️ Clean — No adversarial injection detected")

        print("-" * 65)
        print("STAGE 4: LOCAL AI REVIEW & MAINTAINER DRAFT")
        v_badge = "🟢" if rev.verdict == "Looks good" else ("🟡" if rev.verdict == "Needs work" else "🔴")
        print(f"  Verdict          : {v_badge} {rev.verdict.upper()} ({int(rev.confidence_score * 100)}% confidence)")
        print(f"  Reasoning        : {rev.short_reason}")
        print("-" * 65)
        print("  Educational Maintainer Draft Reply:")
        for line in rev.draft_reply.splitlines():
            print(f"    {line}")

    print("=" * 65 + "\n")


def cmd_check(args: argparse.Namespace) -> None:
    """Handles 'check' command."""
    orchestrator = ShieldOrchestrator()
    print(f"🔍 Fetching and analyzing PR: {args.identifier}...")
    try:
        context = orchestrator.process_pr(args.identifier, persist=True)
        print_scorecard(context)
    except Exception as e:
        print(f"❌ Error analyzing PR: {str(e)}", file=sys.stderr)
        if "Bad credentials" in str(e) or "401" in str(e) or "404" in str(e):
            print("\n💡 Tip: Set your GITHUB_TOKEN environment variable for authenticated requests:")
            print("   $env:GITHUB_TOKEN=\"ghp_your_token_here\"")
            print("   Or test offline scenarios using: python cli.py mock <scenario>")


def cmd_mock(args: argparse.Namespace) -> None:
    """Handles 'mock' command for offline testing & demos."""
    scenario = args.scenario.lower()
    orchestrator = ShieldOrchestrator()

    if scenario == "whitespace":
        mock_ctx = GitHubClient.create_mock_pr(
            pr_id=301,
            title="Update README.md",
            description="",
            files=[
                FileChange(
                    filename="README.md",
                    category="docs",
                    additions=1,
                    deletions=1,
                    status="modified",
                    patch="@@ -10,3 +10,3 @@\n-Hello world\n+Hello world \n",
                )
            ],
            author="spammer-bot",
        )
    elif scenario == "beginner":
        mock_ctx = GitHubClient.create_mock_pr(
            pr_id=302,
            title="fix: typo in function and added fix",
            description="Fixed the bug when user is null.",
            files=[
                FileChange(
                    filename="src/auth.py",
                    category="core",
                    additions=8,
                    deletions=2,
                    status="modified",
                    patch="@@ -5,2 +5,8 @@\n+if user is None:\n+    return None\n",
                )
            ],
            commits=[
                {"sha": "c1a1", "author": "alice", "message": "fix", "date": "2026-10-25T10:00:00Z"},
                {"sha": "c1a2", "author": "alice", "message": "fix2", "date": "2026-10-25T10:05:00Z"},
            ],
            author="alice-newbie",
        )
    elif scenario == "failing_ci":
        mock_ctx = GitHubClient.create_mock_pr(
            pr_id=303,
            title="feat: overhaul database connector",
            description="Refactored database connector. Fixes #88",
            files=[
                FileChange(filename="src/db.py", category="core", additions=150, deletions=40, status="modified"),
                FileChange(filename="tests/test_db.py", category="tests", additions=20, deletions=5, status="modified"),
            ],
            ci_status="failed",
            author="bob-dev",
        )
    else:  # good PR default
        mock_ctx = GitHubClient.create_mock_pr(
            pr_id=300,
            title="fix(api): resolve race condition in token refresh (Fixes #42)",
            description="This PR ensures tokens are safely refreshed atomically. Resolves #42.\n\nIncluded unit tests.",
            files=[
                FileChange(filename="src/token.py", category="core", additions=15, deletions=5, status="modified"),
                FileChange(filename="tests/test_token.py", category="tests", additions=30, deletions=0, status="added"),
            ],
            ci_status="passed",
            author="experienced-dev",
        )

    context = orchestrator.process_pr(f"mock/{scenario}#1", persist=True, mock_context=mock_ctx)
    print_scorecard(context)


def cmd_list(args: argparse.Namespace) -> None:
    """Handles 'list' command."""
    db = ShieldDatabase()
    records = db.list_prs(limit=args.limit, verdict_filter=args.verdict)
    if not records:
        print("No analyzed PRs found in local database.")
        return

    print("\n📦 RECENTLY TRIAGED PRS:")
    print(f"{'PR #':<8} {'AUTHOR':<18} {'SCORE':<8} {'VERDICT':<14} {'TITLE':<38}")
    print("-" * 88)
    for r in records:
        score_val = str(r.get("quick_check_score", "N/A"))
        verdict_val = r.get("ai_verdict", "unreviewed") or "unreviewed"
        title_truncated = (r["title"][:35] + "...") if len(r["title"]) > 35 else r["title"]
        print(f"#{r['pr_id']:<7} @{r['author']:<17} {score_val:<8} {verdict_val:<14} {title_truncated:<38}")
    print()


def cmd_show(args: argparse.Namespace) -> None:
    """Handles 'show' command."""
    db = ShieldDatabase()
    context = db.get_pr(args.pr_id, args.repo)
    if not context:
        print(f"PR #{args.pr_id} not found in database.")
        return
    print(json.dumps(context.model_dump(), indent=2))


def cmd_demo(args: argparse.Namespace) -> None:
    """Handles 'demo' command to run the 8 PR scenario test battery."""
    from demo.run_demo import main as run_demo_main
    sys.argv = ["run_demo.py"]
    if args.pr:
        sys.argv.extend(["--pr", str(args.pr)])
    if args.fast:
        sys.argv.append("--fast")
    if args.ollama:
        sys.argv.append("--ollama")
    run_demo_main()


def cmd_web(args: argparse.Namespace) -> None:
    """Handles 'web' command to launch the Maintainer Shield dashboard."""
    import uvicorn
    print(f"🛡️  Starting Maintainer Shield Web Dashboard on http://{args.host}:{args.port}...")
    uvicorn.run("web.app:app", host=args.host, port=args.port, reload=args.reload)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="shield",
        description="Maintainer Shield: Open-source PR triage assistant",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Command: check / review
    check_p = subparsers.add_parser("check", help="Fetch and run full 4-stage review on a GitHub PR")
    check_p.add_argument("identifier", help="PR URL or owner/repo#number (e.g. owner/repo#10)")

    review_p = subparsers.add_parser("review", help="Alias for check: Run full AI review on a GitHub PR")
    review_p.add_argument("identifier", help="PR URL or owner/repo#number")

    # Command: mock
    mock_p = subparsers.add_parser("mock", help="Run full pipeline on offline mock scenarios")
    mock_p.add_argument("scenario", choices=["good", "whitespace", "beginner", "failing_ci"], help="Scenario name")

    # Command: demo
    demo_p = subparsers.add_parser("demo", help="Run the automated 8-scenario demo evaluation suite")
    demo_p.add_argument("--pr", type=int, choices=range(1, 9), help="Run a specific PR scenario (1 to 8)")
    demo_p.add_argument("--fast", action="store_true", help="High-speed presentation mode")
    demo_p.add_argument("--ollama", action="store_true", help="Run through local Ollama LLM")

    # Command: list
    list_p = subparsers.add_parser("list", help="List triaged PRs from local SQLite store")
    list_p.add_argument("--limit", type=int, default=20, help="Max records to display")
    list_p.add_argument("--verdict", help="Filter by AI verdict (e.g., 'Looks good', 'Needs work')")

    # Command: show
    show_p = subparsers.add_parser("show", help="Display full JSON context for a saved PR")
    show_p.add_argument("pr_id", type=int, help="PR number")
    show_p.add_argument("--repo", help="Repository name (e.g. owner/repo)")

    # Command: web
    web_p = subparsers.add_parser("web", help="Launch the Maintainer Shield web triage dashboard")
    web_p.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    web_p.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    web_p.add_argument("--reload", action="store_true", help="Enable live code reloading")

    args = parser.parse_args()
    if args.command in ("check", "review"):
        cmd_check(args)
    elif args.command == "mock":
        cmd_mock(args)
    elif args.command == "demo":
        cmd_demo(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "web":
        cmd_web(args)


if __name__ == "__main__":
    main()
