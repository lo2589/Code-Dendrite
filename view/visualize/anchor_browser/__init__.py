"""
anchor_browser.py - CD Anchor Browser (compound force graph)
=============================================================
  Left   : file tree
  Center : compound graph — class = large rect containing method circles;
           standalone functions = circles; external callers/callees = dashed circles
  Right  : detail panel for selected node

Usage:
  python anchor_browser.py <project_root_with_.codedendrite> [--output browser.html]
"""

import json
import argparse
from pathlib import Path
from collections import defaultdict

from view.visualize.anchor_browser.dom_sidebar import _HTML
from view.visualize.anchor_browser.build_file_index import _build_file_index, _build_tree, _load_anchors, _read_file_code, _slim, generate, main
from view.visualize.anchor_browser.context import _context, _js, _one_hop, _owner_index, _subtree
from view.visualize.anchor_browser.write_page import _write_page, _write_shell, refresh_page

__all__ = ['_HTML', '_build_file_index', '_build_tree', '_load_anchors', '_read_file_code', '_slim', 'generate', 'main', '_context', '_js', '_one_hop', '_owner_index', '_subtree', '_write_page', '_write_shell', 'refresh_page']
