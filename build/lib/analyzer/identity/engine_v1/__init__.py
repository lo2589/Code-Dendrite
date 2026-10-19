"""
CodeAnchor Engine
-----------------
Binds documentation descriptions to specific code fragments via hash.
When code changes, anchors become stale — agents detect drift before acting.

Anchor format (embedded in any text/markdown/json doc):
    @anchor{id="auth.login" file="src/auth/login.py" symbol="LoginHandler.authenticate" hash="a3f2c1d8"}

Granularity options:
    - file-level:    hash entire file
    - symbol-level:  hash a specific function/class (via AST)
    - line-range:    hash lines N-M
"""

import ast
import hashlib
import json
import re
import textwrap
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────
# Data types
# ─────────────────────────────────────────────

from analyzer.identity.engine_v1.extract_source import ANCHOR_DB, _extract_symbol_source, _extract_lines_source, _short_hash, compute_hash, _ATTR_RE, _TAG_RE
from analyzer.identity.engine_v1.anchor import Anchor, DriftReport, _load_db, _save_db, parse_anchors_from_text, create_anchor, check_drift, refresh_anchor, list_anchors

__all__ = ['ANCHOR_DB', '_extract_symbol_source', '_extract_lines_source', '_short_hash', 'compute_hash', '_ATTR_RE', '_TAG_RE', 'Anchor', 'DriftReport', '_load_db', '_save_db', 'parse_anchors_from_text', 'create_anchor', 'check_drift', 'refresh_anchor', 'list_anchors']
