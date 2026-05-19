"""
inspector.py — 轻量代码导航接口

    list_file_anchors(file_path, root)   → 文件内所有函数/类列表
    find_anchor(keyword, root)           → 按函数名模糊搜索
    get_anchor_source(symbol, root)      → anchor 源码（上下各 +3 行）
    get_anchor_relations(symbol, root)   → 调用者 + 被调用者（一层），带跳转历史
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional


def list_file_anchors(file_path: str, root: str = ".") -> List[dict]:
    """
    列出文件内所有真实 anchor（排除 virtual block）。

    Returns:
        [{symbol, type, line, id}]，按行号排序
    """
    from api.anchors import load_anchors
    anchors = load_anchors(root)
    norm = file_path.replace("\\", "/")
    result = [
        {"symbol": a.symbol, "type": a.symbol_type, "line": a.line_start, "id": a.id}
        for a in anchors.values()
        if not a.is_virtual and norm in a.file.replace("\\", "/")
    ]
    return sorted(result, key=lambda x: x["line"])


def find_anchor(keyword: str, root: str = ".") -> List[dict]:
    """
    按函数名模糊搜索 anchor（不需要知道文件路径）。
    匹配规则：keyword 出现在 symbol 或 file 里（大小写不敏感）。

    Returns:
        [{symbol, type, file, line, id}]，按匹配度排序（精确 > 前缀 > 包含）
    """
    from api.anchors import load_anchors
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


def get_anchor_source(symbol: str, root: str = ".", context: int = 3) -> Optional[dict]:
    """
    返回 anchor 的源码，上下各扩展 context 行。

    Returns:
        {symbol, file, line_start, line_end, actual_start, actual_end, source}
        或 None（找不到 anchor）
    """
    from api.anchors import get_anchor
    anchor = get_anchor(symbol, root)
    if not anchor:
        return None

    file_path = anchor.file
    if not Path(file_path).is_absolute():
        file_path = str(Path(root) / file_path)

    try:
        lines = Path(file_path).read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return None

    lo = max(0, anchor.line_start - 1 - context)
    hi = min(len(lines), anchor.line_end + context)
    numbered = "\n".join(f"{lo + 1 + i:4d}  {line}" for i, line in enumerate(lines[lo:hi]))

    return {
        "symbol": anchor.symbol,
        "file": anchor.file,
        "line_start": anchor.line_start,
        "line_end": anchor.line_end,
        "actual_start": lo + 1,
        "actual_end": hi,
        "source": numbered,
    }


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
    from api.anchors import get_anchor, load_anchors
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
                caller_sym = from_id.split("::")[-1] if "::" in from_id else from_id
                found = get_anchor(caller_sym, root)
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


def get_upward_chain(
    symbol: str,
    root: str = ".",
    max_depth: int = 6,
) -> List[dict]:
    """
    从 symbol 出发，沿 callers 方向往上追，返回整条上行链路。
    每层取所有 callers（不只取一个），按层展开。
    虚拟块 caller 自动透传到真实父函数。

    Returns:
        [
          {"symbol": "Session.get_adapter", "file": "sessions.py", "line": 802, "depth": 0},
          {"symbol": "Session.send",        "file": "sessions.py", "line": 703, "depth": 1},
          ...
        ]
        depth=0 是入口本身，depth 越大越往上。
    """
    from api.anchors import get_anchor, load_anchors
    from api.relations import load_relations

    try:
        rels = load_relations(root)
        edges = rels.get("edges", [])
    except Exception:
        edges = []

    try:
        all_anchors = load_anchors(root)
    except Exception:
        all_anchors = {}

    def _vblock_real_parent(vblock_id: str):
        visited_vb: set = set()
        cur_id = vblock_id
        while cur_id and cur_id not in visited_vb:
            visited_vb.add(cur_id)
            cur = all_anchors.get(cur_id) or all_anchors.get(cur_id.replace("\\", "/"))
            if not cur:
                break
            if not cur.is_virtual:
                return cur
            cur_id = getattr(cur, "parent_anchor", None) or ""
        return None

    def callers_of(sym: str) -> List[dict]:
        anchor = get_anchor(sym, root)
        if not anchor:
            return []
        norm_id = anchor.id.replace("\\", "/")
        seen: set = set()
        result = []
        for edge in edges:
            if edge.get("edge_type") not in ("call", "dataflow"):
                continue
            if edge.get("to_id", "").replace("\\", "/") != norm_id:
                continue
            from_id = edge.get("from_id", "").replace("\\", "/")
            if "#" in from_id:
                real = _vblock_real_parent(from_id)
                if not real:
                    continue
                key = real.id.replace("\\", "/")
                if key in seen:
                    continue
                seen.add(key)
                result.append({
                    "symbol": real.symbol,
                    "file": real.file,
                    "line": real.line_start,
                })
            else:
                if from_id in seen:
                    continue
                seen.add(from_id)
                caller_sym = from_id.split("::")[-1] if "::" in from_id else from_id
                caller_anchor = get_anchor(caller_sym, root)
                if caller_anchor and not caller_anchor.is_virtual:
                    result.append({
                        "symbol": caller_anchor.symbol,
                        "file": caller_anchor.file,
                        "line": caller_anchor.line_start,
                    })
        return result

    chain: List[dict] = []
    visited: set = set()

    entry_anchor = get_anchor(symbol, root)
    if entry_anchor:
        chain.append({
            "symbol": entry_anchor.symbol,
            "file": entry_anchor.file,
            "line": entry_anchor.line_start,
            "depth": 0,
        })
        visited.add(entry_anchor.symbol)
        current_layer = [entry_anchor.symbol]
    else:
        chain.append({"symbol": symbol, "file": None, "line": None, "depth": 0})
        visited.add(symbol)
        current_layer = [symbol]

    for depth in range(1, max_depth + 1):
        next_layer = []
        for sym in current_layer:
            for c in callers_of(sym):
                if c["symbol"] not in visited:
                    visited.add(c["symbol"])
                    chain.append({**c, "depth": depth})
                    next_layer.append(c["symbol"])
        if not next_layer:
            break
        current_layer = next_layer

    return chain


def get_downward_chain(
    symbol: str,
    root: str = ".",
    max_depth: int = 6,
) -> List[dict]:
    """
    从 symbol 出发，沿 callees 方向往下追，返回整条下行链路。
    每层取所有 callees，虚拟块自动透视到叶子真实函数。

    Returns:
        [
          {"symbol": "main",         "file": "main.py", "line": 10, "depth": 0},
          {"symbol": "process_data", "file": "proc.py", "line": 30, "depth": 1},
          ...
        ]
        depth=0 是入口本身，depth 越大越往下。
    """
    from api.anchors import get_anchor, load_anchors
    from api.relations import flatten_virtual

    try:
        all_anchors = load_anchors(root)
    except Exception:
        all_anchors = {}

    def callees_of(anchor_id: str) -> List[dict]:
        anchor = all_anchors.get(anchor_id) or all_anchors.get(anchor_id.replace("\\", "/"))
        if anchor is None:
            anchor = get_anchor(anchor_id, root)
        if not anchor:
            return []
        seen: set = set()
        result = []
        for raw in anchor.callees:
            target = raw.get("target", raw) if isinstance(raw, dict) else raw
            target = str(target or "")
            if not target or target in seen:
                continue
            seen.add(target)
            if "#" in target:
                for leaf in flatten_virtual(target, all_anchors):
                    leaf_id = str(leaf.get("func_id") or "")
                    if not leaf_id or leaf_id in seen:
                        continue
                    seen.add(leaf_id)
                    la = all_anchors.get(leaf_id) or all_anchors.get(leaf_id.replace("\\", "/"))
                    if la and not la.is_virtual:
                        result.append({"id": la.id, "symbol": la.symbol, "file": la.file, "line": la.line_start})
            else:
                norm = target.replace("\\", "/")
                ca = all_anchors.get(norm) or all_anchors.get(target)
                if ca is None:
                    ca = get_anchor(target, root)
                if ca and not ca.is_virtual:
                    result.append({"id": ca.id, "symbol": ca.symbol, "file": ca.file, "line": ca.line_start})
        return result

    chain: List[dict] = []
    visited: set = set()

    entry_anchor = get_anchor(symbol, root)
    if entry_anchor:
        chain.append({
            "id": entry_anchor.id,
            "symbol": entry_anchor.symbol,
            "file": entry_anchor.file,
            "line": entry_anchor.line_start,
            "depth": 0,
        })
        visited.add(entry_anchor.id)
        current_layer = [entry_anchor.id]
    else:
        chain.append({"id": symbol, "symbol": symbol, "file": None, "line": None, "depth": 0})
        visited.add(symbol)
        current_layer = [symbol]

    for depth in range(1, max_depth + 1):
        next_layer = []
        for anchor_id in current_layer:
            for c in callees_of(anchor_id):
                if c["id"] not in visited:
                    visited.add(c["id"])
                    chain.append({**c, "depth": depth})
                    next_layer.append(c["id"])
        if not next_layer:
            break
        current_layer = next_layer

    return chain
