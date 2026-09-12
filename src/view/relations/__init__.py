"""
relation_graph.py - Interactive Relation Graph (Cytoscape.js)
=============================================================
Generates a standalone HTML file with an interactive code relation graph.

Features:
  - Nodes colored by module (file path grouping)
  - Edge colors by type: call/inherit/dataflow/impact/dispatch
  - Click node to expand/collapse neighbors
  - Search box with highlight
  - Drag to reposition nodes (cose layout)
  - Hover tooltip: symbol name, file:line, inputs/outputs
  - Legend panel showing edge type colors
  - Filter checkboxes per edge type

Usage:
  python relation_graph.py <project_root> [--focus node_id] [--radius 2] [--output graph.html]
"""

import json
import argparse
import hashlib
from pathlib import Path
from typing import Optional
from collections import defaultdict


EDGE_COLORS = {
    "call": "#58a6ff",
    "inherit": "#3fb950",
    "dataflow": "#bc8cff",
    "impact": "#f85149",
    "dispatch": "#d29922",
}

MODULE_COLORS = [
    "#264653", "#2a9d8f", "#e9c46a", "#f4a261", "#e76f51",
    "#606c38", "#283618", "#dda15e", "#bc6c25", "#023047",
    "#219ebc", "#8ecae6", "#6d6875", "#b5838d", "#ffb4a2",
    "#588157", "#3a5a40", "#a3b18a", "#344e41", "#dad7cd",
]
IGNORE_PATH_PARTS = {"__pycache__"}
IGNORE_PREFIXES = (".tmp_",)

from view.relations.module import _should_skip_node, _module_color, _get_module, _build_cytoscape_elements, _filter_by_focus
from view.relations.generate_relation_graph import _load_data, _html_template, generate_relation_graph

__all__ = ['_should_skip_node', '_module_color', '_get_module', '_build_cytoscape_elements', '_filter_by_focus', '_load_data', '_html_template', 'generate_relation_graph']
