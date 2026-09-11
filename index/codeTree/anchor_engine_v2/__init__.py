"""
CodeAnchor Engine v2.0 - Industrial Grade
-----------------
Enhanced with:
1. Precise AST symbol extraction (top-level only)
2. Structural Hash mode (ignores whitespace/comments)
3. Drift severity classification
4. Rename detection via fuzzy matching
5. Batch refresh capability
6. Versioned DB with concurrency protection
7. Multi-language support ready
"""

import ast
import hashlib
import json
import re
import textwrap
import tempfile
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Literal
from collections import defaultdict


# ─────────────────────────────────────────────
# Data types
# ─────────────────────────────────────────────

from index.codeTree.anchor_engine_v2.hash import ANCHOR_DB, classify_severity, _find_method_in_class, _find_top_level, _short_hash, _extract_structural_hash, _extract_symbol_source_v2, compute_hash_v2, DB_VERSION, _ATTR_RE, _TAG_RE
from index.codeTree.anchor_engine_v2.load_db import Anchor, DriftReport, _load_db, _save_db, parse_anchors_from_text, create_anchor, check_drift_v2, refresh_anchor, refresh_all_stale, list_anchors, generate_all_anchors
from index.codeTree.anchor_engine_v2.normalize_raw import _normalize_raw

__all__ = ['ANCHOR_DB', 'classify_severity', '_find_method_in_class', '_find_top_level', '_short_hash', '_extract_structural_hash', '_extract_symbol_source_v2', 'compute_hash_v2', 'DB_VERSION', '_ATTR_RE', '_TAG_RE', 'Anchor', 'DriftReport', '_load_db', '_save_db', 'parse_anchors_from_text', 'create_anchor', 'check_drift_v2', 'refresh_anchor', 'refresh_all_stale', 'list_anchors', 'generate_all_anchors', '_normalize_raw']
