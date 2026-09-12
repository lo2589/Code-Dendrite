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

def _normalize_raw(content: str) -> str:
    """
    Raw mode normalization:
    - Strip trailing whitespace
    - Remove empty lines
    - Keep comments and docstrings
    """
    lines = [l.rstrip() for l in content.splitlines() if l.strip()]
    return "\n".join(lines)
