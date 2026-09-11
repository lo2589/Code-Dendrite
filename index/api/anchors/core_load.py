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

from index.api.anchors.subscript_string import ANCHOR_DEFAULTS

def load_anchors(root=".") -> dict:
    """加载 anchors.json，返回 {key: Anchor} 字典"""
    path = Path(root) / ".codedendrite" / "anchors.json"
    if not path.exists():
        raise FileNotFoundError(
            "先执行 generate_all_anchors(root='{}')".format(root)
        )
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    def _coerce_callers(lst):
        result = []
        for item in (lst or []):
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                result.append(item.get("target") or item.get("symbol") or item.get("id") or "")
            else:
                result.append(str(item))
        return result

    def _coerce_callees(lst):
        result = []
        for item in (lst or []):
            if isinstance(item, dict):
                result.append(item)
            elif isinstance(item, str):
                result.append(item)
            else:
                result.append(str(item))
        return result

    result = {}
    for k, v in data.items():
        for field_name, default_value in ANCHOR_DEFAULTS.items():
            if field_name not in v:
                if isinstance(default_value, (list, dict)):
                    v[field_name] = default_value.copy()
                else:
                    v[field_name] = default_value
        v["callers"] = _coerce_callers(v.get("callers"))
        v["callees"] = _coerce_callees(v.get("callees"))
        result[k] = Anchor(**v)
    return result

def filter_anchors_by_file(keyword: str, root: str = ".") -> dict:
    """过滤文件路径包含关键词的锚点。"""
    anchors = load_anchors(root)
    kw = keyword.lower()
    result = {}
    for aid, a in anchors.items():
        f = a.file if hasattr(a, 'file') else a.get('file', '')
        if kw in f.lower():
            result[aid] = a
    return result
