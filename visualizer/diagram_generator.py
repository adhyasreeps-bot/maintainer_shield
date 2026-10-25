"""
visualizer/diagram_generator.py - File Change Treemap and Mermaid Diagram Generator
Member 2 Deliverable: Visualizer Engine for Maintainer Shield.
"""

import re
from typing import Dict, List, Tuple, Any
from core.schemas import FileChange, PRShieldContext, VisualizerData, categorize_file

# Color mapping matching Member 2 specification
CATEGORY_COLORS = {
    "tests": "#10B981",   # Green: Tests (*test*, *spec*, __tests__)
    "docs": "#3B82F6",    # Blue: Documentation (*.md, docs/*, docstrings)
    "core": "#EF4444",    # Red/Coral: Core application logic (src/*, lib/*)
    "config": "#F59E0B",  # Yellow/Orange: Config & build (package.json, pyproject.toml, .github/*)
    "other": "#6B7280",   # Gray: Other assets
}

CATEGORY_ICONS = {
    "tests": "🟩",
    "docs": "🟦",
    "core": "🟥",
    "config": "🟨",
    "other": "⬜",
}


def generate_treemap_data(files: List[FileChange]) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    """
    Computes box-map data where each box size is proportional to lines changed (additions + deletions).
    Returns a list of node dicts and category percentage totals.
    """
    nodes = []
    category_totals = {"core": 0, "tests": 0, "docs": 0, "config": 0, "other": 0}
    grand_total = 0

    for f in files:
        cat = f.category if f.category and f.category != "other" else categorize_file(f.filename)
        changes = max(1, f.additions + f.deletions)  # min size 1 so 0-line diffs stay visible
        category_totals[cat] = category_totals.get(cat, 0) + changes
        grand_total += changes

        nodes.append({
            "filename": f.filename,
            "category": cat,
            "color": CATEGORY_COLORS.get(cat, "#6B7280"),
            "icon": CATEGORY_ICONS.get(cat, "⬜"),
            "additions": f.additions,
            "deletions": f.deletions,
            "total_changes": changes,
        })

    # Calculate percentage shares
    percentages: Dict[str, float] = {}
    for cat, total in category_totals.items():
        percentages[cat] = round((total / grand_total * 100), 1) if grand_total > 0 else 0.0

    for node in nodes:
        node["percentage_of_pr"] = (
            round((node["total_changes"] / grand_total * 100), 1) if grand_total > 0 else 0.0
        )

    # Sort largest changes first for optimal treemap packing
    nodes.sort(key=lambda x: x["total_changes"], reverse=True)
    return nodes, percentages


def generate_mermaid_flowchart(files: List[FileChange]) -> str:
    """
    Generates Mermaid.js flowchart syntax grouping changed files
    into semantic subgraphs with category colors.
    """
    if not files:
        return "flowchart TD\n    empty[\"No files touched in this PR\"]"

    grouped: Dict[str, List[FileChange]] = {}
    for f in files:
        cat = f.category if f.category and f.category != "other" else categorize_file(f.filename)
        grouped.setdefault(cat, []).append(f)

    lines = ["flowchart TD"]

    category_labels = {
        "core": "🟥 Core Application Logic",
        "tests": "🟩 Test Suites & Specs",
        "docs": "🟦 Documentation & Guides",
        "config": "🟨 Config & Build System",
        "other": "⬜ Other Assets",
    }

    node_counter = 1
    for cat, cat_files in grouped.items():
        label = category_labels.get(cat, cat.title())
        lines.append(f'    subgraph sg_{cat} ["{label}"]')
        for cf in cat_files:
            safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', cf.filename)
            node_id = f"f_{node_counter}_{safe_name[:20]}"
            node_label = f"{cf.filename} (+{cf.additions}/-{cf.deletions})"
            lines.append(f'        {node_id}["{node_label}"]')
            node_counter += 1
        lines.append("    end")

    # Mermaid styling
    lines.append("    classDef coreStyle fill:#FEE2E2,stroke:#EF4444,stroke-width:2px,color:#991B1B;")
    lines.append("    classDef testStyle fill:#D1FAE5,stroke:#10B981,stroke-width:2px,color:#065F46;")
    lines.append("    classDef docStyle fill:#DBEAFE,stroke:#3B82F6,stroke-width:2px,color:#1E40AF;")
    lines.append("    classDef configStyle fill:#FEF3C7,stroke:#F59E0B,stroke-width:2px,color:#92400E;")

    return "\n".join(lines)


def build_visualizer_data(
    context: PRShieldContext,
    claim_reality_dict: Dict[str, Any],
    commit_warnings: List[str],
) -> VisualizerData:
    """Combines all visualizer components into the standard VisualizerData schema."""
    treemap_nodes, _ = generate_treemap_data(context.files)
    mermaid_diag = generate_mermaid_flowchart(context.files)

    return VisualizerData(
        mermaid_diagram=mermaid_diag,
        treemap_nodes=treemap_nodes,
        claim_vs_reality=claim_reality_dict,
        commit_pattern_warnings=commit_warnings,
    )


def generate_visualizer_data(context: PRShieldContext) -> VisualizerData:
    """
    Standard entrypoint for the pipeline orchestrator.
    Executes diagram generation, claim vs reality analysis, and commit pattern checks.
    """
    from visualizer.claim_reality import analyze_claim_vs_reality
    from visualizer.commit_graph import detect_commit_patterns

    claim_data = analyze_claim_vs_reality(context.title, context.raw_description, context.files)
    commit_warnings, _ = detect_commit_patterns(context.commits)
    return build_visualizer_data(context, claim_data, commit_warnings)
