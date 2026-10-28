from __future__ import annotations

"""
workflow.py — 端到端 Debug 工作流
===================================
打通：报错 → 大地图 → 小地图 → 关系图 → LLM上下文
"""

import os
import re
from pathlib import Path
from typing import Optional

from analyzer.anchors import load_anchors, get_anchor
from usage.structure.context_builder.builder import ContextBuilder
from usage.structure.context_builder.expander import SymbolExpander

from usage.workflow.extract import _extract_error_line

def _rank_bug_suspects(
    anchors: dict,
    target_anchor,
    relation_edges: list,
    traced_nodes: list[str],
    file_path: str,
    error_msg: str,
    limit: int,
) -> list[dict]:
    line_no = _extract_error_line(error_msg)
    normalized = file_path.replace("\\", "/")
    traced_set = set(traced_nodes)

    candidates = {}

    def ensure(anchor):
        if not anchor:
            return None
        aid = anchor.id
        if aid not in candidates:
            candidates[aid] = {
                "symbol": anchor.symbol,
                "file": anchor.file,
                "line_start": anchor.line_start,
                "line_end": anchor.line_end,
                "symbol_type": anchor.symbol_type,
                "inputs": anchor.inputs,
                "outputs": anchor.outputs,
                "score": 0,
                "reasons": [],
            }
        return candidates[aid]

    if target_anchor:
        entry = ensure(target_anchor)
        entry["score"] += 100
        entry["reasons"].append("target anchor")

    for edge in relation_edges:
        for node_id in (edge.get("from_id", ""), edge.get("to_id", "")):
            anchor = anchors.get(node_id)
            entry = ensure(anchor)
            if not entry:
                continue
            bonus = 12 if edge.get("edge_type") in ("call", "dispatch") else 8
            entry["score"] += bonus
            entry["reasons"].append(f"relation:{edge.get('edge_type')}")

    for symbol in traced_set:
        for a in anchors.values():
            if a.symbol == symbol or a.symbol.endswith("." + symbol):
                entry = ensure(a)
                if entry:
                    entry["score"] += 30
                    entry["reasons"].append("on traced path")
                break

    for anchor in anchors.values():
        if not (anchor.file == normalized or anchor.file.endswith(normalized)):
            continue
        entry = ensure(anchor)
        if not entry:
            continue
        entry["score"] += 15
        entry["reasons"].append("same file")

        if line_no is not None:
            if anchor.line_start <= line_no <= anchor.line_end:
                entry["score"] += 60
                entry["reasons"].append("contains error line")
            else:
                distance = min(abs(anchor.line_start - line_no), abs(anchor.line_end - line_no))
                if distance <= 5:
                    entry["score"] += 25
                    entry["reasons"].append("near error line")

    suspects = sorted(
        candidates.values(),
        key=lambda item: (-item["score"], item["file"], item["line_start"]),
    )

    # Do not turn a file-scope hint into an edit recommendation.  Keep the
    # result empty until a line, explicit target, relation, or traced path
    # provides discriminating evidence.
    if suspects and all(set(item["reasons"]) <= {"same file"} for item in suspects):
        return []

    for suspect in suspects:
        seen = []
        unique_reasons = []
        for reason in suspect["reasons"]:
            if reason not in seen:
                seen.append(reason)
                unique_reasons.append(reason)
        suspect["reasons"] = unique_reasons

    return suspects[:limit]

def _refresh_navigation(root: str) -> None:
    """查询前刷新锚点和关系图，保持导航数据最新。"""
    try:
        from analyzer.anchors import generate_all_anchors
        generate_all_anchors(root)
    except Exception:
        pass

    try:
        from api.relations import generate_relations
        generate_relations(root)
    except Exception:
        pass

    try:
        from usage.structure.module_tree import generate_module_summary, generate_module_tree
        generate_module_tree(root)
        generate_module_summary(root)
    except Exception:
        pass

def _resolve_target_anchor(
    target_symbol: Optional[str],
    error_msg: str,
    file_path: str,
    root: str,
    anchors: dict,
):
    """优先根据显式目标和错误位置定位；文件路径本身不冒充函数证据。"""
    if target_symbol:
        anchor = get_anchor(target_symbol, root=root)
        if anchor:
            return anchor

    try:
        from usage.smart import smart_analyze
        report = smart_analyze(error_msg, file=file_path, severity="high", root=root)
        report_target = str(getattr(report, "target", "") or "").replace("\\", "/")
        # SmartAnalyzer may return the input file path as its generic target.
        # A file narrows the search area but is not evidence for any one symbol.
        looks_like_anchor = "::" in report_target
        looks_like_file = (
            "/" in report_target
            or report_target.endswith((".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".cpp", ".cc", ".c", ".h"))
        )
        if report_target and (looks_like_anchor or not looks_like_file):
            anchor = get_anchor(report_target, root=root)
            if anchor:
                return anchor
    except Exception:
        pass

    line_no = _extract_error_line(error_msg)
    normalized = file_path.replace("\\", "/")
    file_anchors = [
        a for a in anchors.values()
        if a.file == normalized or a.file.endswith(normalized)
    ]
    if not file_anchors:
        return None

    if line_no is not None:
        containing = [
            a for a in file_anchors
            if a.line_start <= line_no <= a.line_end
        ]
        if containing:
            containing.sort(key=lambda a: (a.line_end - a.line_start, a.line_start))
            return containing[0]

        file_anchors.sort(key=lambda a: min(abs(a.line_start - line_no), abs(a.line_end - line_no)))
        return file_anchors[0]

    # File-only evidence cannot distinguish one function from its siblings.
    return None

def _trace_bug_path(
    root: str,
    entry_anchor,
    target_anchor,
    anchors: dict,
    conditions: dict,
):
    try:
        if not entry_anchor or not target_anchor:
            return [], None

        from collections import deque
        from api.relations import load_relations

        data = load_relations(root)
        start_id = entry_anchor.id
        target_id = target_anchor.id

        queue = deque([(start_id, [start_id])])
        visited = {start_id}

        while queue:
            current, path = queue.popleft()
            if current == target_id:
                symbols = [anchors[node_id].symbol for node_id in path if node_id in anchors]
                summary = " → ".join(symbols) + f"  （{len(symbols)} 个节点）"
                return symbols, summary

            for edge in data.get("edges", []):
                if edge.get("from_id") != current:
                    continue
                if edge.get("edge_type") not in ("call", "dispatch", "dataflow"):
                    continue
                if edge.get("edge_type") == "dispatch":
                    dispatch_key = edge.get("dispatch_key")
                    dispatch_value = edge.get("dispatch_value")
                    if dispatch_key in conditions and conditions[dispatch_key] != dispatch_value:
                        continue
                nxt = edge.get("to_id")
                if not nxt or nxt in visited:
                    continue
                visited.add(nxt)
                queue.append((nxt, path + [nxt]))
    except Exception:
        pass

    try:
        from analyzer.path.tracer import PathTracer

        tracer = PathTracer(root)
        result = (
            tracer
            .from_entry(entry_anchor.symbol)
            .until(target_anchor.symbol)
            ._run_with(conditions)
        )
        return result.get_path_names(), result.summary()
    except Exception:
        return [], None

def debug_workflow(error_msg: str, file_path: str, root: str) -> dict:
    """
    端到端 Debug 工作流

    参数：
        error_msg: 报错信息
        file_path: 出错的文件路径（相对或绝对）
        root: 项目根目录

    返回：
        {
            error, target,
            big_map, small_map,
            relations,
            callers, callees,
            inputs, outputs, mro, overrides
        }
    """
    cb = ContextBuilder(root)
    ex = SymbolExpander(root)

    # 第一步：大地图（LLM 模式，带 anchor:// 引用）
    big_map = cb.build_map(budget_tokens=2000, mode="llm")

    # 第二步：定位报错函数
    target = None
    try:
        from usage.smart import smart_analyze
        report = smart_analyze(error_msg, file=file_path, severity="high", root=root)
        target = getattr(report, "target", None)
    except Exception:
        target = None

    if not target:
        import os
        target = os.path.splitext(os.path.basename(file_path))[0]

    # 第三步：小地图（以报错函数为中心）
    small_map = cb.build_debug_map(target)

    # 第四步：定位锚点，构建关系子图（radius=1）
    anchor = get_anchor(target, root=root)
    node_id = "{}::{}".format(anchor.file, anchor.symbol) if anchor else target

    try:
        from api.relations import expand_node
        relations = expand_node(node_id, root=root, radius=1)
    except Exception:
        relations = {}

    # 第五步：用 expand_with_relations 拿完整摘要
    anchor_ref = (
        "anchor://{}::{}".format(anchor.file, anchor.symbol)
        if anchor else target
    )
    full = ex.expand_with_relations(anchor_ref, radius=1)

    return {
        "error": error_msg,
        "target": target,
        "big_map": big_map,
        "small_map": small_map,
        "relations": relations,
        "callers": full.get("callers", []),
        "callees": full.get("callees", []),
        "inputs": full.get("inputs", []),
        "outputs": full.get("outputs", []),
        "mro": full.get("mro", []),
        "overrides": full.get("overrides"),
    }
