"""
Relations API.

Generate and query the persisted relation graph in `.codedendrite/relations.json`.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

from base.shared.types import Edge

from relate.api.relations.load_relations import __all__, _norm, _build_id_index, _build_unique_symbol_index, _callee_target, _iter_call_refs, _build_virtual_skip_pairs, _callee_condition, _callee_seq, _edge_hash, _is_virtual_id, _resolve_id, load_relations, count_edge_types, get_node_edges, flatten_virtual, expand_node, filter_edges_by_keyword
from relate.api.relations.generate_relations import generate_relations

__all__ = ['__all__', '_norm', '_build_id_index', '_build_unique_symbol_index', '_callee_target', '_iter_call_refs', '_build_virtual_skip_pairs', '_callee_condition', '_callee_seq', '_edge_hash', '_is_virtual_id', '_resolve_id', 'load_relations', 'count_edge_types', 'get_node_edges', 'flatten_virtual', 'expand_node', 'filter_edges_by_keyword', 'generate_relations']
