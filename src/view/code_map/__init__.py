"""
code_map.py - Interactive Code Map (D3.js Treemap)
===================================================
Generates an interactive HTML treemap showing the project structure.
Modules are rectangles sized by symbol count, colored by edge frequency (hotspot).

Features:
  - Treemap layout: modules as rectangles, sized by symbol count
  - Heat coloring: cold (blue) to hot (red) based on total edge count
  - Click module to expand and show internal functions
  - Hover tooltip: module name, symbol count, edge count
  - Zoom/pan support
  - Click function to link to relation graph

Usage:
  python code_map.py <project_root> [--output codemap.html]
"""

import json
import argparse
from pathlib import Path
from typing import Optional
from collections import defaultdict


IGNORE_PATH_PARTS = {"__pycache__"}
IGNORE_PREFIXES = (".tmp_",)

from view.code_map.build_treemap_data import _should_skip_file, _build_treemap_data
from view.code_map.generate_code_map import _load_data, _html_template, generate_code_map

__all__ = ['_should_skip_file', '_build_treemap_data', '_load_data', '_html_template', 'generate_code_map']
