"""
module_tree.py - Phase 1 static semantic module tree
====================================================

Phase 1 goals:
  - build .codedendrite/module_tree.json from anchors + relations
  - compute a stable call_structure_hash
  - avoid any LLM dependency
  - provide a light-weight module layer for build_map() section 0
"""

from __future__ import annotations

import ast
import hashlib
import json
from collections import Counter, defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from analyzer.anchors import load_anchors


ENTRY_NOISE_PREFIXES = (
    "_",
    "test_",
    "demo",
    "debug",
    "helper",
    "util",
    "internal",
    "banner",
    "section",
)
STOP_SYMBOL_PREFIXES = (
    "_load",
    "_parse",
    "_read",
    "_write",
    "_format",
    "_build",
    "_get",
    "_set",
)
STOP_DIR_PARTS = {"tests", "utils", "helpers", "examples", "__pycache__"}
EXPAND_EDGE_TYPES = {"call", "dispatch"}
SUMMARY_VERSION = 3

from usage.structure.module_tree.backfill_module_tree_responsibilities import __all__, _attach_cross_module_edges, _backfill_module_tree_responsibilities, _build_responsibility_hint, _camel_to_snake, _guess_module_name, _should_stop_at_symbol, _walk_module, _jaccard, _merge_raw_modules, _merge_entry_functions, _merge_named_modules, _merge_singleton_islands, _symbol_source_dir, _rebuild_membership, _pick_primary_entry, _refresh_module_names
from usage.structure.module_tree.compute_call_structure_hash import _build_semantic_modules, _find_cli_entries, _call_name, _collect_dispatch_sources, _collect_dispatch_targets, _compute_call_structure_hash, _is_noise_anchor, _normalize_symbol_id, _normalize_anchors, _normalize_relations, _normalize_symbol_word, _read_json, _render_project_summary
from usage.structure.module_tree.module import _score_entries, _summarize_module, _summarize_project, load_module_tree, find_module_for_symbol, generate_module_summary, generate_module_tree, get_module, load_summary_cache, query_modules

__all__ = ['__all__', '_attach_cross_module_edges', '_backfill_module_tree_responsibilities', '_build_responsibility_hint', '_camel_to_snake', '_guess_module_name', '_should_stop_at_symbol', '_walk_module', '_jaccard', '_merge_raw_modules', '_merge_entry_functions', '_merge_named_modules', '_merge_singleton_islands', '_symbol_source_dir', '_rebuild_membership', '_pick_primary_entry', '_refresh_module_names', '_build_semantic_modules', '_find_cli_entries', '_call_name', '_collect_dispatch_sources', '_collect_dispatch_targets', '_compute_call_structure_hash', '_is_noise_anchor', '_normalize_symbol_id', '_normalize_anchors', '_normalize_relations', '_normalize_symbol_word', '_read_json', '_render_project_summary', '_score_entries', '_summarize_module', '_summarize_project', 'load_module_tree', 'find_module_for_symbol', 'generate_module_summary', 'generate_module_tree', 'get_module', 'load_summary_cache', 'query_modules']
