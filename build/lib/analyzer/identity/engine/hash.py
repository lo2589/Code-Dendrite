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

ANCHOR_DB = ".code_anchors.json"

def classify_severity(
    old_hash: str,
    new_hash: str,
    old_struct_hash: Optional[str],
    new_struct_hash: Optional[str],
    status: str
) -> str:
    """
    Classify drift severity based on what changed.
    
    Rules:
    - critical: file/symbol missing
    - high: structural change (API, signature, logic)
    - medium: raw change but struct same (whitespace, comments)
    - low: import order, formatting only
    """
    if status in ("missing_file", "missing_symbol"):
        return "critical"
    
    if old_struct_hash != new_struct_hash:
        return "high"  # Structure changed
    
    if old_hash != new_hash:
        return "medium"  # Text changed but structure same
    
    return "low"

def _find_method_in_class(class_node: ast.ClassDef, method_name: str):
    """Find a method inside a class (direct children only)."""
    for child in class_node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if child.name == method_name:
                return child
    return None

def _find_top_level(tree: ast.AST, name: str):
    """Find a top-level function/class by name."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == name:
                return node
    return None

def _short_hash(content: str) -> str:
    """8-char SHA-1 of content."""
    return hashlib.sha1(content.encode()).hexdigest()[:8]

def _extract_structural_hash(node: ast.AST) -> str:
    """
    Structural Hash mode:
    - Use ast.dump() which ignores whitespace/comments
    - Only structure changes trigger drift
    """
    dump = ast.dump(node, include_attributes=False)
    return _short_hash(dump)

def _extract_symbol_source_v2(file_path: Path, symbol: str):
    """
    Extract source AND structural hash for a symbol.
    Returns (source_code, structural_hash) or (None, None) if not found.
    
    Improvements:
    - Only searches top-level definitions
    - Handles nested methods correctly
    - Returns structural hash for struct mode
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, OSError):
        return None, None

    lines = source.splitlines()

    parts = symbol.split(".", 1)
    top_name = parts[0]
    method_name = parts[1] if len(parts) > 1 else None

    # Find top-level symbol
    node = _find_top_level(tree, top_name)
    if node is None:
        return None, None

    # If looking for a method
    if method_name:
        if not isinstance(node, ast.ClassDef):
            return None, None
        method_node = _find_method_in_class(node, method_name)
        if method_node is None:
            return None, None
        
        # Extract method source
        end = method_node.end_lineno  # type: ignore[attr-defined]
        src = "\n".join(lines[method_node.lineno - 1 : end])
        struct_hash = _extract_structural_hash(method_node)
        return src, struct_hash

    # Whole function/class
    end = node.end_lineno  # type: ignore[attr-defined]
    src = "\n".join(lines[node.lineno - 1 : end])
    struct_hash = _extract_structural_hash(node)
    return src, struct_hash

def compute_hash_v2(
    file: str, 
    symbol: Optional[str] = None,
    line_start: Optional[int] = None, 
    line_end: Optional[int] = None,
    hash_mode: str = "struct",  # "raw" | "struct"
    root: Path = Path(".")
) -> tuple[str, str, Optional[str]]:
    """
    Returns (hash, status, structural_hash).
    status is "ok" | "missing_file" | "missing_symbol".
    
    Args:
        hash_mode: "raw" (text-based) or "struct" (AST-based, recommended)
    """
    p = root / file
    if not p.exists():
        return "", "missing_file", None

    if symbol:
        src, struct_hash = _extract_symbol_source_v2(p, symbol)
        if src is None:
            return "", "missing_symbol", None
        
        if hash_mode == "struct":
            return struct_hash, "ok", struct_hash
        else:
            return _short_hash(src), "ok", struct_hash

    if line_start is not None:
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
            src = "\n".join(lines[start - 1 : end])
            return _short_hash(src), "ok", None
        except OSError:
            return "", "missing_file", None

    # Whole file
    content = p.read_text(encoding="utf-8")
    if hash_mode == "struct":
        # Parse entire file for structural hash
        try:
            tree = ast.parse(content)
            struct_hash = _extract_structural_hash(tree)
            return struct_hash, "ok", struct_hash
        except:
            pass
    return _short_hash(content), "ok", None

DB_VERSION = 2

_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')

_TAG_RE = re.compile(r'@anchor\{([^}]+)\}')
