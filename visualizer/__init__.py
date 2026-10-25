"""
Maintainer Shield Visualizer Package (Member 2 Deliverable).
Provides diagram generation, treemaps, claim vs reality analysis,
and commit graph hygiene pattern detection.
"""

from visualizer.diagram_generator import (
    generate_mermaid_flowchart,
    generate_treemap_data,
    build_visualizer_data,
    generate_visualizer_data,
)
from visualizer.claim_reality import analyze_claim_vs_reality
from visualizer.commit_graph import (
    detect_commit_patterns,
    generate_commit_timeline,
)

__all__ = [
    "generate_mermaid_flowchart",
    "generate_treemap_data",
    "build_visualizer_data",
    "generate_visualizer_data",
    "analyze_claim_vs_reality",
    "detect_commit_patterns",
    "generate_commit_timeline",
]
