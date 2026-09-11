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

from index.api.anchors.build_effective_methods_table import _apply_inheritance_refs, _build_effective_methods_table
from index.api.anchors.resolve import _finalize_anchor_graph, _normalize_file_ref
from index.api.anchors.core_anchor import _generate_anchors_for_paths, _write_anchors
from index.api.anchors.core_load import load_anchors

def resolve_anchor_candidates(symbol: str, root=".") -> List[Anchor]:
    """Resolve a query without silently choosing between ambiguous short names.

    Matching precedence is the same as :func:`get_anchor`: exact ID, exact
    symbol, then method/ID suffix.  Only the first non-empty tier is returned.
    """
    anchors = load_anchors(root)
    if symbol in anchors:
        return [anchors[symbol]]

    exact_ids = [a for a in anchors.values() if a.id == symbol]
    if exact_ids:
        return exact_ids

    exact_symbols = [a for a in anchors.values() if a.symbol == symbol]
    if exact_symbols:
        return exact_symbols

    suffix_matches = [
        a
        for a in anchors.values()
        if a.symbol.endswith("." + symbol) or a.id.endswith("::" + symbol)
    ]
    return list({a.id: a for a in suffix_matches}.values())

def get_anchor(symbol: str, root=".") -> Optional[Anchor]:
    """按完整 anchor ID 或唯一符号名查找锚点；歧义时返回 ``None``。"""
    candidates = resolve_anchor_candidates(symbol, root)
    return candidates[0] if len(candidates) == 1 else None

def list_all_symbols(root, extensions=(".py",), exclude_dirs=None):
    from synth.codeTree.deep_drift import _list_all_symbols
    return _list_all_symbols(root, extensions, exclude_dirs)

def list_anchors(root="."):
    from index.codeTree.anchor_engine_v2 import list_anchors as _list_anchors
    return _list_anchors(root)

def list_anchors_in_file(
    file_path: str,
    root: str = ".",
    include_virtual: bool = False,
    symbol_types: Optional[List[str]] = None,
) -> dict:
    """列出单个文件内的 anchors，默认不含 virtual_block。"""
    anchors = load_anchors(root)
    normalized = file_path.replace("\\", "/").lower()
    result = {}
    allowed = set(symbol_types or ["function", "method", "class", "module"])
    for aid, anchor in anchors.items():
        anchor_file = (anchor.file if hasattr(anchor, "file") else anchor.get("file", "")).replace("\\", "/")
        if anchor_file.lower() != normalized:
            continue
        anchor_type = anchor.symbol_type if hasattr(anchor, "symbol_type") else anchor.get("symbol_type", "")
        is_virtual = anchor.is_virtual if hasattr(anchor, "is_virtual") else anchor.get("is_virtual", False)
        if is_virtual and not include_virtual:
            continue
        if allowed and anchor_type not in allowed and not (include_virtual and anchor_type == "virtual_block"):
            continue
        result[aid] = anchor
    return result

def search_anchors(keyword: str, root=".", file_prefix: str = None,
                   symbol_type: str = None, top_n: int = None) -> List[Anchor]:
    """
    模糊搜索锚点，返回匹配列表。

    参数：
        keyword     — 在 symbol 名中做子串匹配（空字符串 = 不过滤）
        root        — 目标项目路径
        file_prefix — 只返回该文件路径前缀下的锚点，如 "api" / "src/trainer"
        symbol_type — 只返回指定类型："function" / "method" / "class"
        top_n       — 最多返回 N 条
    """
    anchors = load_anchors(root)
    results = []
    for a in anchors.values():
        if keyword and keyword not in a.symbol:
            continue
        if file_prefix and not a.file.startswith(file_prefix):
            continue
        if symbol_type and a.symbol_type != symbol_type:
            continue
        results.append(a)
        if top_n and len(results) >= top_n:
            break
    return results

def update_anchors_for_files(root=".", changed_files=None, include_virtual_blocks=False) -> dict:
    root = Path(root)
    changed_files = changed_files or []
    ignore = CodeDendriteIgnore(str(root))
    normalized_changed = {
        _normalize_file_ref(root, f)
        for f in changed_files
    }

    try:
        anchors = load_anchors(str(root))
    except FileNotFoundError:
        anchors = {}

    before = len(anchors)
    old_ids_in_changed_files = {
        key
        for key, anchor in anchors.items()
        if _normalize_file_ref(root, anchor.file) in normalized_changed
    }
    file_paths = []
    for rel in sorted(normalized_changed):
        path = root / rel
        if path.exists() and path.is_file() and ignore.should_scan(path):
            file_paths.append(path)

    new_anchors, failed, completed_files = _generate_anchors_for_paths(
        root,
        file_paths,
        include_virtual_blocks=include_virtual_blocks,
    )
    # Replace a file atomically only after its adapter completed.  A parser
    # error therefore cannot erase the last known-good anchors for that file.
    removable_ids = {
        key for key in old_ids_in_changed_files
        if _normalize_file_ref(root, anchors[key].file) in completed_files
    }
    anchors = {
        key: anchor for key, anchor in anchors.items()
        if key not in removable_ids
    }
    removed = len(removable_ids)
    anchors.update(new_anchors)

    # Self, callers, and callees all need a fresh resolve pass — not the
    # whole graph:
    #   - self:    every anchor the rescan just produced (new_ids) — added
    #              or changed, we can't tell which cheaply and don't need to.
    #   - callees: covered by the same pass, since resolving an anchor's own
    #              call sites is what "self" means here.
    #   - callers: any anchor elsewhere whose call_sites already target an id
    #              that got added, changed, or removed by this update
    #              (removed_ids) — its edge may now point at nothing, or
    #              a moved/renamed target may now exist under a new id.
    #   - retries: any anchor with a call site that never resolved in an
    #              earlier pass, in case the target exists now — these are
    #              kept (not dropped) by _finalize_anchor_graph specifically
    #              so this retry is possible.
    new_ids = set(new_anchors.keys())
    removed_ids = removable_ids - new_ids
    touched_ids = new_ids | removed_ids
    affected_ids = set(new_ids)
    try:
        from serve.api.bridges import apply_runtime_bridges
        affected_ids.update(apply_runtime_bridges(root, anchors))
    except Exception as e:
        failed.append("runtime_bridges: {}".format(e))
    for anchor in anchors.values():
        if anchor.id in affected_ids:
            continue
        needs_retry = False
        for site in (anchor.call_sites or []):
            if not isinstance(site, dict):
                continue
            target = str(site.get("target") or "")
            if target in touched_ids:
                needs_retry = True
                break
            if "::" not in target:
                needs_retry = True
        if needs_retry:
            affected_ids.add(anchor.id)

    try:
        from relate.inheritance import build_class_index, compute_mro, find_subclasses
        index = build_class_index(str(root))
        _apply_inheritance_refs(anchors, index, compute_mro, find_subclasses)
        _build_effective_methods_table(anchors)
    except Exception as e:
        failed.append("inheritance: {}".format(e))
    _finalize_anchor_graph(anchors, only_ids=affected_ids, root=root)
    _write_anchors(root, anchors)

    return {
        "before": before,
        "removed": removed,
        "created": len(new_anchors),
        "total_anchors": len(anchors),
        "resolved": len(affected_ids),
        "failed": len(failed),
        "errors": failed,
    }
