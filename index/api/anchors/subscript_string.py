"""
锚点管理接口层
========================
generate_all_anchors: 从 5 个源 merge，写入 .codedendrite/anchors.json
load_anchors / get_anchor: 唯一读取接口
"""

import json
import os
import ast
import re as _re
from dataclasses import asdict
from pathlib import Path
from typing import Optional, List, Dict

from base.shared.types import Anchor
from base.shared.codedendrite_ignore import CodeDendriteIgnore
from base.shared.formula_skip import should_skip as _should_skip_formula

_EMBED_STYLE_RE = _re.compile(r'<style[^>]*>(.*?)</style>', _re.DOTALL | _re.IGNORECASE)
_EMBED_SCRIPT_RE = _re.compile(r'<script[^>]*>(.*?)</script>', _re.DOTALL | _re.IGNORECASE)
_EMBED_DOM_ID_RE = _re.compile(r'\bid=["\']([A-Za-z][\w-]*)["\']')
_EMBED_CSS_SEL_RE = _re.compile(r'(?:^|[\s,>+~])([.#][A-Za-z][\w-]*)', _re.MULTILINE)
_EMBED_JS_FUNC_RE = _re.compile(r'function\s+([A-Za-z$_][\w$]*)\s*\(')
_EMBED_JS_QUERY_RE = _re.compile(r'(?:querySelectorAll?|getElementById)\s*\(\s*["\']([^"\']+)["\']')

# ── 调试日志（环境变量 CD_ANCHOR_LOG 开关；默认不打，不污染生产 run）──
import time as _time
_ANCHOR_DBG = bool(os.environ.get("CD_ANCHOR_LOG"))

ANCHOR_DEFAULTS = {
    "code": "",
    "callers": [],
    "callees": [],
    "call_sites": [],
    "inputs": [],
    "outputs": [],
    "parent_classes": [],
    "overrides": None,
    "overridden_by": [],
    "mro": [],
    "own_methods": [],
    "effective_methods": {},
    "observations": [],
    "language": "python",
    "description": "",
    "drift": "ok",
    "is_virtual": False,
    "virtual_kind": None,
    "parent_anchor": None,
    "scope_label": None,
    "block_metadata": {},
    "registered_as": None,
    "column_start": 0,
    "column_end": 0,
    "qualified_name": "",
    "signature": "",
    "imports": [],
}

BUILTIN_NOISE = {
    "print", "append", "get", "len", "str", "int", "list", "dict",
    "set", "type", "range", "enumerate", "zip", "map", "filter",
    "isinstance", "hasattr", "getattr", "setattr", "open", "any",
    "all", "sorted", "reversed", "join", "split", "format", "update",
    "extend", "items", "values", "keys", "pop", "insert", "read",
    "write", "close", "encode", "decode", "replace", "strip",
    # super() 及常见 dunder：callee 解析结果不可用，过滤掉
    "super", "__init__", "__new__", "__str__", "__repr__",
    "__len__", "__iter__", "__next__", "__enter__", "__exit__",
    "__getitem__", "__setitem__", "__delitem__", "__contains__",
    "__call__", "__del__",
}

def _subscript_string(node: ast.AST) -> str:
    if not isinstance(node, ast.Subscript):
        return ""
    value = node.slice
    if hasattr(ast, "Index") and isinstance(value, ast.Index):
        value = value.value
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return ""
