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

from usage.workflow.build_minimal_verification_step import _align_modules_with_suspects, _build_edit_scope, _build_edit_targets, _build_fix_hypothesis, _build_minimal_verification_step, _build_proposed_steps, _build_risk_notes
from usage.workflow.extract import _build_verification_steps, _extract_relevant_branches, _extract_relevant_variables, _get_anchor_from_suspect, _locate_relevant_modules
from usage.workflow.resolve_target_anchor import _rank_bug_suspects, _refresh_navigation, _resolve_target_anchor, _trace_bug_path

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
            from analyzer.dataflow.language.python.analyzer import analyze_function_flow
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
