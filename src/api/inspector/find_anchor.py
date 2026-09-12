"""
inspector.py — 轻量代码导航接口

    list_file_anchors(file_path, root)   → 文件内所有函数/类列表
    find_anchor(keyword, root)           → 按函数名模糊搜索
    get_anchor_source(symbol, root)      → anchor 源码（上下各 +3 行）
    get_anchor_relations(symbol, root)   → 调用者 + 被调用者（一层），带跳转历史
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Optional

def _current_python_range(
    source: str,
    symbol: str,
    indexed_start: int,
    indexed_end: int,
) -> tuple[int, int]:
    """Recover the current AST range when an older index stored a one-line anchor."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return indexed_start, indexed_end

    parent_by_id = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_by_id[id(child)] = parent

    node_types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    leaf_name = symbol.rsplit(".", 1)[-1]
    candidates = [
        node
        for node in ast.walk(tree)
        if isinstance(node, node_types) and node.name == leaf_name
    ]
    if not candidates:
        return indexed_start, indexed_end

    same_line = [
        node for node in candidates
        if int(getattr(node, "lineno", 0) or 0) == indexed_start
    ]
    if len(same_line) == 1:
        node = same_line[0]
        return node.lineno, int(getattr(node, "end_lineno", None) or node.lineno)

    def qualified_name(node: ast.AST) -> str:
        names = [getattr(node, "name", "")]
        parent = parent_by_id.get(id(node))
        while parent is not None:
            if isinstance(parent, ast.ClassDef):
                names.append(parent.name)
            parent = parent_by_id.get(id(parent))
        return ".".join(reversed([name for name in names if name]))

    exact_symbol = [node for node in candidates if qualified_name(node) == symbol]
    if len(exact_symbol) == 1:
        node = exact_symbol[0]
        return node.lineno, int(getattr(node, "end_lineno", None) or node.lineno)
    return indexed_start, indexed_end

def find_anchor(keyword: str, root: str = ".") -> List[dict]:
    """
    按函数名模糊搜索 anchor（不需要知道文件路径）。
    匹配规则：keyword 出现在 symbol 或 file 里（大小写不敏感）。

    Returns:
        [{symbol, type, file, line, id}]，按匹配度排序（精确 > 前缀 > 包含）
    """
    from analyzer.anchors import load_anchors
    anchors = load_anchors(root)
    kw = keyword.lower()

    exact, prefix, contains = [], [], []
    for a in anchors.values():
        if a.is_virtual:
            continue
        sym_lower = a.symbol.lower()
        entry = {"symbol": a.symbol, "type": a.symbol_type,
                 "file": a.file, "line": a.line_start, "id": a.id}
        if sym_lower == kw:
            exact.append(entry)
        elif sym_lower.endswith("." + kw) or sym_lower.startswith(kw):
            prefix.append(entry)
        elif kw in sym_lower or kw in a.file.lower():
            contains.append(entry)

    return exact + prefix + contains

def find_attribute_call_sites(
    method_name: str,
    root: str = ".",
    limit: int = 50,
) -> List[dict]:
    """Find lexical ``receiver.method(...)`` sites without claiming type resolution.

    These are deliberately returned as candidates rather than call-graph edges:
    Python AST can see the attribute name but usually cannot prove the runtime
    type of ``receiver``.
    """
    from analyzer.anchors import load_anchors

    root_path = Path(root).resolve()
    anchors = load_anchors(root)
    python_files = sorted({
        a.file.replace("\\", "/")
        for a in anchors.values()
        if a.language == "python" and a.file.endswith(".py")
    })
    results = []
    for relative_file in python_files:
        source_path = Path(relative_file)
        if not source_path.is_absolute():
            source_path = root_path / source_path
        try:
            source = source_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (OSError, SyntaxError, ValueError):
            continue
        lines = source.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr != method_name:
                continue
            try:
                receiver = ast.unparse(func.value)
            except Exception:
                receiver = "?"
            line = int(getattr(node, "lineno", 0) or 0)
            results.append({
                "file": relative_file,
                "line": line,
                "receiver": receiver,
                "expression": lines[line - 1].strip() if 0 < line <= len(lines) else "",
            })
    return sorted(results, key=lambda item: (item["file"], item["line"]))[:limit]

def get_anchor_relations(
    symbol: str,
    root: str = ".",
    history: Optional[List[str]] = None,
    error_line: Optional[int] = None,
) -> Optional[dict]:
    """
    查询 anchor 的一层调用关系，方便跳转。
    callers 优先从 relations.json 反查（比 anchor.callers 覆盖更全），
    callees 从 anchor.callees 读（已包含 AST 分析结果），保留 seq/condition/line。

    Args:
        symbol:     函数名（短名或全格式 file::symbol）
        root:       项目根目录
        history:    上一跳传来的 visited_chain，自动追加当前 symbol
        error_line: 报错行号，只返回 line <= error_line 的 callee（报错点及之前）

    Returns:
        {
            current:  {symbol, file, line_start, line_end},
            callers:  [{symbol, file, line, id, resolved, seq}],
            callees:  [{symbol, file, line, id, resolved, seq, condition, scope_label}],
            visited_chain: [symbol, ...]
        }
        或 None（找不到 anchor）
    """
    from analyzer.anchors import get_anchor, load_anchors
    from api.relations import load_relations

    anchor = get_anchor(symbol, root)
    if not anchor:
        return None

    try:
        all_anchors = load_anchors(root)
    except Exception:
        all_anchors = {}

    def _ref_name(ref) -> str:
        if isinstance(ref, dict):
            ref = ref.get("target") or ref.get("id") or ref.get("symbol") or ""
        return str(ref)

    def resolve_callee(raw) -> dict:
        name = _ref_name(raw)
        meta = raw if isinstance(raw, dict) else {}
        found = get_anchor(name, root)
        base = {
            "seq": meta.get("seq"),
            "condition": meta.get("condition"),
            "scope_label": meta.get("scope_label"),
            "is_conditional": meta.get("is_conditional", False),
            "callee_line": meta.get("line"),
        }
        if found:
            return {**base, "symbol": found.symbol, "file": found.file,
                    "line": found.line_start, "id": found.id, "resolved": True}
        return {**base, "symbol": name, "file": None, "line": None, "id": None, "resolved": False}

    # callers：从 relations 反查 to_id == anchor.id 的边
    # 虚拟块 caller 透传：沿 parent_anchor 找到真实函数，携带 condition/scope_label
    callers = []
    try:
        rels = load_relations(root)
        norm_id = anchor.id.replace("\\", "/")
        seen: set = set()

        def _vblock_real_parent(vblock_id: str):
            """沿 parent_anchor 链向上，返回第一个非虚拟 anchor，或 None。"""
            visited: set = set()
            cur_id = vblock_id
            while cur_id and cur_id not in visited:
                visited.add(cur_id)
                cur = all_anchors.get(cur_id) or all_anchors.get(cur_id.replace("\\", "/"))
                if not cur:
                    break
                if not cur.is_virtual:
                    return cur
                cur_id = getattr(cur, "parent_anchor", None) or ""
            return None

        for edge in rels.get("edges", []):
            if edge.get("edge_type") not in ("call", "dataflow"):
                continue
            to_id = edge.get("to_id", "").replace("\\", "/")
            if to_id != norm_id:
                continue
            from_id = edge.get("from_id", "").replace("\\", "/")
            condition = edge.get("condition")
            scope_label = edge.get("scope_label")
            seq_list = edge.get("seq", [])

            if "#" in from_id:
                # 虚拟块 caller：透传到真实父函数，保留条件信息
                real = _vblock_real_parent(from_id)
                if not real:
                    continue
                dedup_key = (real.id.replace("\\", "/"), condition, scope_label)
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                callers.append({
                    "symbol": real.symbol, "file": real.file,
                    "line": real.line_start, "id": real.id,
                    "resolved": True, "seq": seq_list,
                    "condition": condition, "scope_label": scope_label,
                    "via_vblock": True,
                })
            else:
                if from_id in seen:
                    continue
                seen.add(from_id)
                found = get_anchor(from_id, root)
                if found:
                    callers.append({
                        "symbol": found.symbol, "file": found.file,
                        "line": found.line_start, "id": found.id,
                        "resolved": True, "seq": seq_list,
                        "condition": None, "scope_label": None, "via_vblock": False,
                    })
                else:
                    callers.append({
                        "symbol": caller_sym, "file": None, "line": None,
                        "id": None, "resolved": False, "seq": seq_list,
                        "condition": None, "scope_label": None, "via_vblock": False,
                    })
    except Exception:
        callers = [{"symbol": str(c), "file": None, "line": None,
                    "id": None, "resolved": False, "seq": [],
                    "condition": None, "scope_label": None, "via_vblock": False}
                   for c in anchor.callers]

    # callees：从 anchor.callees 读，只给最外层（直接子项，含虚拟块）
    # error_line 裁剪：虚拟块整块 line_start > error_line 则跳过；普通 callee 的 line > error_line 则跳过
    raw_callees = anchor.callees
    if error_line is not None and raw_callees:
        filtered = []
        for c in raw_callees:
            meta = c if isinstance(c, dict) else {}
            target = meta.get("target", c) if isinstance(c, dict) else c
            callee_line = meta.get("line")
            if "#" in str(target):
                vblock = all_anchors.get(str(target))
                if vblock and vblock.line_start > error_line:
                    continue
            elif callee_line is not None and callee_line > error_line:
                continue
            filtered.append(c)
        raw_callees = filtered

    visited_chain = list(history or [])
    if anchor.symbol not in visited_chain:
        visited_chain.append(anchor.symbol)

    return {
        "current": {
            "symbol": anchor.symbol,
            "file": anchor.file,
            "line_start": anchor.line_start,
            "line_end": anchor.line_end,
        },
        "callers": callers,
        "callees": [resolve_callee(c) for c in raw_callees],
        "visited_chain": visited_chain,
    }
