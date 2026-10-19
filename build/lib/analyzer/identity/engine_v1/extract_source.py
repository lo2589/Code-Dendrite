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

ANCHOR_DB = ".code_anchors.json"

def _extract_symbol_source(file_path: Path, symbol: str) -> Optional[str]:
    """
    Extract source of a top-level function or class (or Class.method) via AST.
    Returns None if symbol not found.
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, OSError):
        return None

    lines = source.splitlines()

    parts = symbol.split(".", 1)
    top_name = parts[0]
    method_name = parts[1] if len(parts) > 1 else None

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == top_name:
                if method_name is None:
                    # whole function/class
                    end = node.end_lineno  # type: ignore[attr-defined]
                    return "\n".join(lines[node.lineno - 1 : end])
                elif isinstance(node, ast.ClassDef):
                    # look for method inside class
                    for child in ast.walk(node):
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if child.name == method_name:
                                end = child.end_lineno  # type: ignore[attr-defined]
                                return "\n".join(lines[child.lineno - 1 : end])
    return None

def _extract_lines_source(file_path: Path, start: int, end: int) -> Optional[str]:
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
        return "\n".join(lines[start - 1 : end])
    except OSError:
        return None

def _short_hash(content: str) -> str:
    """8-char SHA-1 of normalized content (strips comments/blank lines for stability)."""
    lines = [l.rstrip() for l in content.splitlines() if l.strip()]
    normalized = "\n".join(lines)
    return hashlib.sha1(normalized.encode()).hexdigest()[:8]

def compute_hash(file: str, symbol: Optional[str] = None,
                 line_start: Optional[int] = None, line_end: Optional[int] = None,
                 root: Path = Path(".")) -> tuple[str, str]:
    """
    Returns (hash, status) where status is "ok" | "missing_file" | "missing_symbol".
    """
    p = root / file
    if not p.exists():
        return "", "missing_file"

    if symbol:
        src = _extract_symbol_source(p, symbol)
        if src is None:
            return "", "missing_symbol"
        return _short_hash(src), "ok"

    if line_start is not None:
        src = _extract_lines_source(p, line_start, line_end or line_start)
        if src is None:
            return "", "missing_file"
        return _short_hash(src), "ok"

    # whole file
    return _short_hash(p.read_text(encoding="utf-8")), "ok"

_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')

_TAG_RE = re.compile(r'@anchor\{([^}]+)\}')
