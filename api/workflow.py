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

from api.anchors import load_anchors, get_anchor
from context_builder.builder import ContextBuilder
from context_builder.expander import SymbolExpander


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
        from api.smart import smart_analyze
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


def locate_bug(
    error_msg: str,
    file_path: str,
    root: str,
    entry_symbol: Optional[str] = None,
    target_symbol: Optional[str] = None,
    conditions: Optional[dict] = None,
    refresh: bool = True,
    limit: int = 5,
) -> dict:
    """
    函数级问题定位器。

    目标：
        从错误信息 / 文件路径 / 可选入口函数出发，
        给出一个按可疑度排序的函数节点列表。
    """
    if refresh:
        _refresh_navigation(root)

    conditions = conditions or {}
    anchors = load_anchors(root)

    target_anchor = _resolve_target_anchor(
        target_symbol=target_symbol,
        error_msg=error_msg,
        file_path=file_path,
        root=root,
        anchors=anchors,
    )
    target_id = (
        f"{target_anchor.file}::{target_anchor.symbol}"
        if target_anchor else None
    )
    related_modules = _locate_relevant_modules(
        root=root,
        file_path=file_path,
        error_msg=error_msg,
        entry_symbol=entry_symbol,
        target_anchor=target_anchor,
        conditions=conditions,
        limit=max(limit, 3),
    )

    relation_graph = {}
    relation_edges = []
    if target_id:
        try:
            from api.relations import expand_node
            relation_graph = expand_node(target_id, root=root, radius=1)
            relation_edges = relation_graph.get("edges", [])
        except Exception:
            relation_graph = {}
            relation_edges = []

    traced_nodes = []
    trace_summary = None
    if entry_symbol and target_anchor:
        entry_anchor = get_anchor(entry_symbol, root=root)
        traced_nodes, trace_summary = _trace_bug_path(
            root=root,
            entry_anchor=entry_anchor,
            target_anchor=target_anchor,
            anchors=anchors,
            conditions=conditions,
        )

    suspects = _rank_bug_suspects(
        anchors=anchors,
        target_anchor=target_anchor,
        relation_edges=relation_edges,
        traced_nodes=traced_nodes,
        file_path=file_path,
        error_msg=error_msg,
        limit=limit,
    )
    related_modules = _align_modules_with_suspects(
        related_modules=related_modules,
        suspects=suspects,
        root=root,
    )

    return {
        "error": error_msg,
        "file": file_path,
        "entry_symbol": entry_symbol,
        "target_symbol": target_anchor.symbol if target_anchor else target_symbol,
        "target_id": target_id,
        "related_modules": related_modules,
        "top_module": related_modules[0] if related_modules else None,
        "trace_summary": trace_summary,
        "trace_nodes": traced_nodes,
        "relation_graph": relation_graph,
        "suspects": suspects,
    }


def diagnose_bug(
    error_msg: str,
    file_path: str,
    root: str,
    entry_symbol: Optional[str] = None,
    target_symbol: Optional[str] = None,
    conditions: Optional[dict] = None,
    refresh: bool = True,
    limit: int = 5,
) -> dict:
    """
    在 locate_bug() 之上补充函数级诊断信息，形成更接近修复闭环的输出。
    """
    diagnosis = locate_bug(
        error_msg=error_msg,
        file_path=file_path,
        root=root,
        entry_symbol=entry_symbol,
        target_symbol=target_symbol,
        conditions=conditions,
        refresh=refresh,
        limit=limit,
    )

    suspects = diagnosis.get("suspects", [])
    if not suspects:
        diagnosis.update({
            "top_suspect": None,
            "suspect_reasons": [],
            "relevant_variables": [],
            "relevant_branches": [],
            "minimal_verification_step": None,
            "suggested_edit_scope": None,
        })
        return diagnosis

    conditions = conditions or {}
    anchors = load_anchors(root)
    top_suspect = suspects[0]
    top_anchor = _get_anchor_from_suspect(top_suspect, anchors)

    flow = None
    if top_anchor:
        try:
            from dataFlow.analyzer import analyze_function_flow
            flow = analyze_function_flow(str(Path(root) / top_anchor.file), top_anchor.symbol)
        except Exception:
            flow = None

    relevant_branches = _extract_relevant_branches(
        diagnosis=diagnosis,
        top_anchor=top_anchor,
        conditions=conditions,
    )
    relevant_variables = _extract_relevant_variables(
        top_suspect=top_suspect,
        flow=flow,
        conditions=conditions,
        branches=relevant_branches,
    )
    minimal_verification_step = _build_minimal_verification_step(
        entry_symbol=entry_symbol,
        top_suspect=top_suspect,
        branches=relevant_branches,
        conditions=conditions,
        trace_summary=diagnosis.get("trace_summary"),
    )
    suggested_edit_scope = _build_edit_scope(
        top_suspect=top_suspect,
        diagnosis=diagnosis,
        branches=relevant_branches,
    )

    diagnosis.update({
        "top_suspect": top_suspect,
        "suspect_reasons": top_suspect.get("reasons", []),
        "relevant_variables": relevant_variables,
        "relevant_branches": relevant_branches,
        "minimal_verification_step": minimal_verification_step,
        "suggested_edit_scope": suggested_edit_scope,
    })
    return diagnosis


def plan_fix(
    error_msg: str,
    file_path: str,
    root: str,
    entry_symbol: Optional[str] = None,
    target_symbol: Optional[str] = None,
    conditions: Optional[dict] = None,
    refresh: bool = True,
    limit: int = 5,
) -> dict:
    """
    在 diagnose_bug() 之上生成更偏执行层的修复计划。
    """
    diagnosis = diagnose_bug(
        error_msg=error_msg,
        file_path=file_path,
        root=root,
        entry_symbol=entry_symbol,
        target_symbol=target_symbol,
        conditions=conditions,
        refresh=refresh,
        limit=limit,
    )

    top_suspect = diagnosis.get("top_suspect")
    if not top_suspect:
        diagnosis.update({
            "fix_hypothesis": None,
            "proposed_steps": [],
            "verification_steps": [],
            "edit_targets": [],
            "risk_notes": [],
        })
        return diagnosis

    relevant_branches = diagnosis.get("relevant_branches", [])
    relevant_variables = diagnosis.get("relevant_variables", [])
    suggested_scope = diagnosis.get("suggested_edit_scope") or {}
    top_branch = next((b for b in relevant_branches if b.get("matches_conditions")), None)

    fix_hypothesis = _build_fix_hypothesis(
        top_suspect=top_suspect,
        top_branch=top_branch,
        relevant_variables=relevant_variables,
    )
    proposed_steps = _build_proposed_steps(
        top_suspect=top_suspect,
        top_branch=top_branch,
        diagnosis=diagnosis,
    )
    verification_steps = _build_verification_steps(
        diagnosis=diagnosis,
        top_branch=top_branch,
    )
    edit_targets = _build_edit_targets(
        top_suspect=top_suspect,
        suggested_scope=suggested_scope,
    )
    risk_notes = _build_risk_notes(
        diagnosis=diagnosis,
        top_branch=top_branch,
    )

    diagnosis.update({
        "fix_hypothesis": fix_hypothesis,
        "proposed_steps": proposed_steps,
        "verification_steps": verification_steps,
        "edit_targets": edit_targets,
        "risk_notes": risk_notes,
    })
    return diagnosis


def verify_fix(
    error_msg: str,
    file_path: str,
    root: str,
    entry_symbol: Optional[str] = None,
    target_symbol: Optional[str] = None,
    conditions: Optional[dict] = None,
    edited_files: Optional[list[str]] = None,
    edited_symbols: Optional[list[str]] = None,
    refresh: bool = True,
    limit: int = 5,
) -> dict:
    """
    在 plan_fix() 之上生成修复后的验证计划。

    说明：
        该接口当前负责组织“修完之后怎么验证”，
        还不自动执行具体测试或自动改代码。
    """
    fix_plan = plan_fix(
        error_msg=error_msg,
        file_path=file_path,
        root=root,
        entry_symbol=entry_symbol,
        target_symbol=target_symbol,
        conditions=conditions,
        refresh=refresh,
        limit=limit,
    )

    top_suspect = fix_plan.get("top_suspect")
    edited_files = edited_files or []
    edited_symbols = edited_symbols or []

    primary_file = (fix_plan.get("suggested_edit_scope") or {}).get("primary_file")
    primary_symbol = (fix_plan.get("suggested_edit_scope") or {}).get("primary_symbol")

    coverage = {
        "primary_file_edited": bool(primary_file and primary_file in edited_files),
        "primary_symbol_edited": bool(primary_symbol and primary_symbol in edited_symbols),
        "edited_files": edited_files,
        "edited_symbols": edited_symbols,
    }

    verification_checklist = _build_verification_checklist(fix_plan)
    success_criteria = _build_success_criteria(fix_plan)
    follow_up_queries = _build_follow_up_queries(fix_plan)
    residual_risks = _build_residual_risks(fix_plan, coverage)

    fix_plan.update({
        "verification_checklist": verification_checklist,
        "success_criteria": success_criteria,
        "follow_up_queries": follow_up_queries,
        "edit_coverage": coverage,
        "residual_risks": residual_risks,
        "verification_summary": (
            f"Verify `{top_suspect['symbol']}` first, then re-check the affected route and nearby sibling branches."
            if top_suspect else
            "Re-run navigation and route checks after the edit."
        ),
    })
    return fix_plan


def run_debug_loop(
    error_msg: str,
    file_path: str,
    root: str,
    entry_symbol: Optional[str] = None,
    target_symbol: Optional[str] = None,
    conditions: Optional[dict] = None,
    edited_files: Optional[list[str]] = None,
    edited_symbols: Optional[list[str]] = None,
    refresh: bool = True,
    limit: int = 5,
) -> dict:
    """
    统一 Debug 闭环入口。

    组织：
        navigation -> locate -> diagnose -> plan -> verify
    """
    workflow_result = verify_fix(
        error_msg=error_msg,
        file_path=file_path,
        root=root,
        entry_symbol=entry_symbol,
        target_symbol=target_symbol,
        conditions=conditions,
        edited_files=edited_files,
        edited_symbols=edited_symbols,
        refresh=refresh,
        limit=limit,
    )

    loop_summary = _build_debug_loop_summary(workflow_result)
    next_action = _build_next_action(workflow_result)

    workflow_result.update({
        "loop_stage": "verify",
        "module_summary": _build_module_summary(workflow_result),
        "loop_summary": loop_summary,
        "next_action": next_action,
    })
    return workflow_result


def _locate_relevant_modules(
    root: str,
    file_path: str,
    error_msg: str,
    entry_symbol: Optional[str],
    target_anchor,
    conditions: dict,
    limit: int,
) -> list[dict]:
    try:
        from api.module_tree import (
            generate_module_summary,
            generate_module_tree,
            find_module_for_symbol,
            get_module,
            query_modules,
        )
    except Exception:
        return []

    try:
        generate_module_tree(root)
        generate_module_summary(root)
    except Exception:
        pass

    candidates = []
    seen = set()

    def add(module, reason: str, bonus: int):
        if not module:
            return
        module_id = module.get("id")
        if not module_id:
            return
        if module_id not in seen:
            seen.add(module_id)
            candidates.append(
                {
                    "id": module_id,
                    "name": module.get("name"),
                    "responsibility": module.get("responsibility") or module.get("responsibility_hint"),
                    "entry_functions": module.get("entry_functions", []),
                    "score": bonus,
                    "reasons": [reason],
                }
            )
            return
        for item in candidates:
            if item["id"] == module_id:
                item["score"] += bonus
                if reason not in item["reasons"]:
                    item["reasons"].append(reason)
                return

    if target_anchor:
        add(find_module_for_symbol(target_anchor.id, root=root), "target symbol", 8)
        add(find_module_for_symbol(target_anchor.symbol, root=root), "target name", 5)
        file_module = get_module(_module_name_from_file(target_anchor.file), root=root)
        add(file_module, "target file", 3)

    if entry_symbol:
        add(find_module_for_symbol(entry_symbol, root=root), "entry symbol", 6)

    file_query = Path(file_path).stem.replace("_", " ")
    if file_query:
        for module in query_modules(file_query, root=root, limit=3):
            add(module, f"file query:{file_query}", 2)

    for token in _extract_module_query_terms(error_msg, conditions):
        for module in query_modules(token, root=root, limit=3):
            add(module, f"query:{token}", 1)

    candidates.sort(key=lambda item: (-item["score"], item["name"] or ""))
    return candidates[:limit]


def _extract_module_query_terms(error_msg: str, conditions: dict) -> list[str]:
    terms = []
    for value in conditions.values():
        if isinstance(value, str) and value:
            terms.append(value.replace("_", " "))

    text = error_msg or ""
    for match in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text):
        lowered = match.lower()
        if lowered in {"error", "runtime", "line", "when", "method", "near"}:
            continue
        terms.append(match.replace("_", " "))

    deduped = []
    seen = set()
    for term in terms:
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(term)
    return deduped[:8]


def _module_name_from_file(file_path: str) -> str:
    stem = Path(file_path).stem
    parts = [part for part in stem.split("_") if part]
    return "_".join(parts[:3]) if parts else stem


def _align_modules_with_suspects(
    related_modules: list[dict],
    suspects: list[dict],
    root: str,
) -> list[dict]:
    try:
        from api.module_tree import find_module_for_symbol
    except Exception:
        return related_modules

    if not suspects:
        return related_modules

    by_id = {module.get("id"): dict(module) for module in related_modules}

    def boost(module, reason: str, bonus: int):
        if not module:
            return
        module_id = module.get("id")
        if not module_id:
            return
        payload = by_id.get(module_id)
        if payload is None:
            payload = {
                "id": module_id,
                "name": module.get("name"),
                "responsibility": module.get("responsibility") or module.get("responsibility_hint"),
                "entry_functions": module.get("entry_functions", []),
                "score": 0,
                "reasons": [],
            }
            by_id[module_id] = payload
        payload["score"] = payload.get("score", 0) + bonus
        reasons = payload.setdefault("reasons", [])
        if reason not in reasons:
            reasons.append(reason)

    for index, suspect in enumerate(suspects[:3]):
        symbol = suspect.get("symbol")
        file_path = suspect.get("file")
        if not symbol:
            continue
        module = find_module_for_symbol(symbol, root=root)
        boost(module, f"suspect:{symbol}", 6 - index)
        if file_path:
            module = find_module_for_symbol(f"{file_path}::{symbol}", root=root)
            boost(module, f"suspect-id:{symbol}", 8 - index)

    aligned = list(by_id.values())
    aligned.sort(key=lambda item: (-item.get("score", 0), item.get("name") or ""))
    return aligned


def _refresh_navigation(root: str) -> None:
    """查询前刷新锚点和关系图，保持导航数据最新。"""
    try:
        from api.anchors import generate_all_anchors
        generate_all_anchors(root)
    except Exception:
        pass

    try:
        from api.relations import generate_relations
        generate_relations(root)
    except Exception:
        pass

    try:
        from api.module_tree import generate_module_summary, generate_module_tree
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
    """优先根据显式目标，其次根据错误定位，最后回退到文件内最相关函数。"""
    if target_symbol:
        anchor = get_anchor(target_symbol, root=root)
        if anchor:
            return anchor

    try:
        from api.smart import smart_analyze
        report = smart_analyze(error_msg, file=file_path, severity="high", root=root)
        anchor = get_anchor(getattr(report, "target", "") or "", root=root)
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

    file_anchors.sort(key=lambda a: (0 if a.symbol_type in ("function", "method") else 1, a.line_start))
    return file_anchors[0]


def _extract_error_line(error_msg: str) -> Optional[int]:
    match = re.search(r"line (\d+)", error_msg or "")
    return int(match.group(1)) if match else None


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
        from pathTracer.tracer import PathTracer

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


def _get_anchor_from_suspect(suspect: dict, anchors: dict):
    symbol = suspect.get("symbol")
    file_path = suspect.get("file")
    for anchor in anchors.values():
        if anchor.symbol != symbol:
            continue
        if anchor.file == file_path or anchor.file.endswith(file_path):
            return anchor
    return None


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

    for suspect in suspects:
        seen = []
        unique_reasons = []
        for reason in suspect["reasons"]:
            if reason not in seen:
                seen.append(reason)
                unique_reasons.append(reason)
        suspect["reasons"] = unique_reasons

    return suspects[:limit]


def _extract_relevant_branches(
    diagnosis: dict,
    top_anchor,
    conditions: dict,
) -> list[dict]:
    branches = []
    relation_graph = diagnosis.get("relation_graph", {}) or {}
    edges = relation_graph.get("edges", [])
    target_id = diagnosis.get("target_id")
    top_id = top_anchor.id if top_anchor else None

    for edge in edges:
        if edge.get("edge_type") != "dispatch":
            continue
        if top_id and edge.get("from_id") != top_id and edge.get("to_id") != top_id:
            if not (target_id and (edge.get("from_id") == target_id or edge.get("to_id") == target_id)):
                continue

        item = {
            "from_id": edge.get("from_id"),
            "to_id": edge.get("to_id"),
            "condition": edge.get("condition"),
            "dispatch_key": edge.get("dispatch_key"),
            "dispatch_value": edge.get("dispatch_value"),
            "matches_conditions": (
                edge.get("dispatch_key") in conditions
                and conditions.get(edge.get("dispatch_key")) == edge.get("dispatch_value")
            ),
        }
        branches.append(item)

    branches.sort(key=lambda item: (not item["matches_conditions"], item.get("condition") or ""))
    return branches


def _extract_relevant_variables(
    top_suspect: dict,
    flow,
    conditions: dict,
    branches: list[dict],
) -> list[dict]:
    seen = set()
    items = []

    def add(name: str, source: str, detail=None):
        if not name or name in seen:
            return
        seen.add(name)
        payload = {"name": name, "source": source}
        if detail is not None:
            payload["detail"] = detail
        items.append(payload)

    for item in top_suspect.get("inputs", []):
        add(item.get("name"), "function_input", item.get("type"))

    for item in top_suspect.get("outputs", []):
        add(item.get("name"), "function_output", item.get("type"))

    if flow:
        for trans in flow.transformations[:5]:
            add(trans.to_var, "transformation_target", trans.code_snippet)
            add(trans.from_var, "transformation_source", trans.code_snippet)
        for call in flow.calls[:5]:
            add(call.target, "called_function", call.code_snippet)

    for key, value in conditions.items():
        add(key, "runtime_condition", repr(value))

    for branch in branches[:5]:
        add(branch.get("dispatch_key"), "dispatch_key", branch.get("condition"))
        add(branch.get("dispatch_value"), "dispatch_value", branch.get("condition"))

    return items


def _build_minimal_verification_step(
    entry_symbol: Optional[str],
    top_suspect: dict,
    branches: list[dict],
    conditions: dict,
    trace_summary: Optional[str],
) -> str:
    if branches:
        matched = next((b for b in branches if b.get("matches_conditions")), branches[0])
        cond_text = matched.get("condition") or "dispatch condition"
        branch_target = (matched.get("to_id") or "").split("::")[-1] or top_suspect["symbol"]
        return (
            f"Re-run from `{entry_symbol or top_suspect['symbol']}` with {conditions or cond_text}, "
            f"then verify the `{cond_text}` branch reaches `{branch_target}`."
        )

    if trace_summary:
        return (
            f"Re-run the path `{trace_summary}` and confirm the failure is reproducible at "
            f"`{top_suspect['symbol']}` before editing."
        )

    return (
        f"Reproduce the error in `{top_suspect['file']}` and confirm the failure lands inside "
        f"`{top_suspect['symbol']}` before changing code."
    )


def _build_edit_scope(
    top_suspect: dict,
    diagnosis: dict,
    branches: list[dict],
) -> dict:
    related_symbols = [top_suspect["symbol"]]
    for suspect in diagnosis.get("suspects", [])[1:4]:
        if suspect["symbol"] not in related_symbols:
            related_symbols.append(suspect["symbol"])

    branch_conditions = []
    for branch in branches:
        condition = branch.get("condition")
        if condition and condition not in branch_conditions:
            branch_conditions.append(condition)

    return {
        "primary_file": top_suspect["file"],
        "primary_symbol": top_suspect["symbol"],
        "line_start": top_suspect["line_start"],
        "line_end": top_suspect["line_end"],
        "nearby_symbols": related_symbols[1:],
        "branch_conditions": branch_conditions[:5],
    }


def _build_fix_hypothesis(
    top_suspect: dict,
    top_branch: Optional[dict],
    relevant_variables: list[dict],
) -> str:
    branch_text = top_branch.get("condition") if top_branch else None
    variable_names = [item["name"] for item in relevant_variables[:4] if item.get("name")]

    if branch_text:
        return (
            f"The bug likely sits in `{top_suspect['symbol']}` around the `{branch_text}` route, "
            f"where variables such as {', '.join(variable_names) or 'the request payload'} are prepared before dispatch."
        )

    return (
        f"The bug likely sits inside `{top_suspect['symbol']}` near its local data preparation / branching logic "
        f"before control flows into downstream handlers."
    )


def _build_proposed_steps(
    top_suspect: dict,
    top_branch: Optional[dict],
    diagnosis: dict,
) -> list[str]:
    steps = [
        f"Inspect `{top_suspect['symbol']}` in `{top_suspect['file']}` first; keep the edit scoped to lines {top_suspect['line_start']}-{top_suspect['line_end']}.",
    ]

    if top_branch and top_branch.get("condition"):
        steps.append(
            f"Check whether the `{top_branch['condition']}` branch builds the correct inputs before dispatching to `{(top_branch.get('to_id') or '').split('::')[-1]}`."
        )

    nearby = diagnosis.get("suggested_edit_scope", {}).get("nearby_symbols", [])
    if nearby:
        steps.append(
            f"Only inspect neighbor symbols if needed: {', '.join(nearby[:3])}."
        )

    steps.append(
        "Prefer a local fix in the top suspect function before touching downstream handlers or broad shared utilities."
    )
    return steps


def _build_verification_steps(
    diagnosis: dict,
    top_branch: Optional[dict],
) -> list[str]:
    steps = []
    minimal = diagnosis.get("minimal_verification_step")
    if minimal:
        steps.append(minimal)

    if top_branch and top_branch.get("condition"):
        steps.append(
            f"Verify the non-matching sibling branches still stay unchanged after the fix, especially routes adjacent to `{top_branch['condition']}`."
        )

    top = diagnosis.get("top_suspect")
    if top:
        steps.append(
            f"Re-check `diagnose_bug()` or `locate_bug()` after the edit and confirm `{top['symbol']}` is no longer the dominant suspect for the same failure."
        )

    return steps


def _build_edit_targets(
    top_suspect: dict,
    suggested_scope: dict,
) -> list[dict]:
    targets = [{
        "file": top_suspect["file"],
        "symbol": top_suspect["symbol"],
        "line_start": top_suspect["line_start"],
        "line_end": top_suspect["line_end"],
        "priority": "primary",
    }]

    for symbol in suggested_scope.get("nearby_symbols", [])[:3]:
        targets.append({
            "file": suggested_scope.get("primary_file", top_suspect["file"]),
            "symbol": symbol,
            "priority": "secondary",
        })

    return targets


def _build_risk_notes(
    diagnosis: dict,
    top_branch: Optional[dict],
) -> list[str]:
    notes = []

    branch_conditions = diagnosis.get("suggested_edit_scope", {}).get("branch_conditions", [])
    if len(branch_conditions) > 1:
        notes.append(
            "This function fans out into multiple dispatch branches, so a broad refactor may regress unrelated routes."
        )

    if top_branch and top_branch.get("dispatch_key"):
        notes.append(
            f"The route key `{top_branch['dispatch_key']}` is shared across sibling handlers; preserve existing semantics for non-target values."
        )

    relevant_variables = diagnosis.get("relevant_variables", [])
    if any(item.get("name") == "request" for item in relevant_variables):
        notes.append(
            "The request object is part of the suspect data path, so validate field extraction and default handling carefully."
        )

    return notes


def _build_verification_checklist(fix_plan: dict) -> list[str]:
    checklist = []

    for step in fix_plan.get("verification_steps", []):
        checklist.append(step)

    top = fix_plan.get("top_suspect")
    if top:
        checklist.append(
            f"Read the final version of `{top['symbol']}` and confirm the changed logic is still scoped to `{top['file']}` lines {top['line_start']}-{top['line_end']}."
        )

    for branch in fix_plan.get("relevant_branches", [])[:3]:
        if branch.get("matches_conditions"):
            checklist.append(
                f"Confirm the matching branch `{branch['condition']}` still routes to `{(branch.get('to_id') or '').split('::')[-1]}` after the edit."
            )
            break

    return checklist


def _build_success_criteria(fix_plan: dict) -> list[str]:
    criteria = []

    top = fix_plan.get("top_suspect")
    if top:
        criteria.append(
            f"The original failure is no longer reproducible in `{top['symbol']}`."
        )

    for branch in fix_plan.get("relevant_branches", [])[:2]:
        if branch.get("matches_conditions"):
            criteria.append(
                f"The route `{branch['condition']}` reaches the expected target `{(branch.get('to_id') or '').split('::')[-1]}`."
            )
            break

    criteria.append(
        "No unrelated sibling branch behavior regresses when re-checking the same dispatch function."
    )
    return criteria


def _build_follow_up_queries(fix_plan: dict) -> list[str]:
    queries = []
    top = fix_plan.get("top_suspect")
    if top:
        queries.append(f"expand {top['file']}::{top['symbol']}")
        queries.append(top["symbol"])

    for branch in fix_plan.get("relevant_branches", [])[:2]:
        if branch.get("dispatch_value"):
            queries.append(branch["dispatch_value"])

    deduped = []
    for item in queries:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _build_residual_risks(fix_plan: dict, coverage: dict) -> list[str]:
    risks = list(fix_plan.get("risk_notes", []))

    if coverage.get("edited_files") and not coverage.get("primary_file_edited"):
        risks.append(
            "The declared edits do not include the primary suspect file, so the fix may be incomplete or mis-scoped."
        )

    if coverage.get("edited_symbols") and not coverage.get("primary_symbol_edited"):
        risks.append(
            "The declared edits do not include the top suspect symbol, so the main failure path may still be untouched."
        )

    if not coverage.get("edited_files") and not coverage.get("edited_symbols"):
        risks.append(
            "No edited files or symbols were supplied, so verification is planning-only and not tied to a concrete patch set yet."
        )

    return risks


def _build_debug_loop_summary(workflow_result: dict) -> str:
    top = workflow_result.get("top_suspect")
    branch = next(
        (b for b in workflow_result.get("relevant_branches", []) if b.get("matches_conditions")),
        None,
    )

    if top and branch:
        return (
            f"Primary focus is `{top['symbol']}` in `{top['file']}`, "
            f"especially the `{branch['condition']}` branch leading to "
            f"`{(branch.get('to_id') or '').split('::')[-1]}`."
        )
    if top:
        return (
            f"Primary focus is `{top['symbol']}` in `{top['file']}`; "
            f"use the generated verification checklist before broadening scope."
        )
    return "No dominant suspect was found; refresh navigation data and broaden the search scope."


def _build_module_summary(workflow_result: dict) -> str:
    modules = workflow_result.get("related_modules", [])
    if not modules:
        return "No semantic module matched the current failure context."

    top = modules[0]
    entries = [
        item.get("symbol_id", "").split("::")[-1]
        for item in top.get("entry_functions", [])
        if item.get("symbol_id")
    ]
    entry_text = " / ".join(entries[:2]) if entries else "no entry hint"
    return (
        f"Most relevant module is `{top.get('name')}`: "
        f"{top.get('responsibility') or 'module summary pending'} "
        f"(entries: {entry_text})."
    )


def _build_next_action(workflow_result: dict) -> dict:
    top = workflow_result.get("top_suspect")
    scope = workflow_result.get("suggested_edit_scope") or {}
    verification = workflow_result.get("verification_checklist", [])

    if not top:
        return {
            "type": "re-scan",
            "message": "Refresh indexes and rerun locate_bug() with a more specific file path or entry symbol.",
        }

    return {
        "type": "edit_and_verify",
        "primary_symbol": top.get("symbol"),
        "primary_file": scope.get("primary_file", top.get("file")),
        "message": (
            f"Edit `{top['symbol']}` first, keep the patch local, then execute the first verification step."
        ),
        "first_verification_step": verification[0] if verification else None,
    }
