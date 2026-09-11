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

from index.api.anchors import load_anchors, get_anchor
from synth.context_builder.builder import ContextBuilder
from synth.context_builder.expander import SymbolExpander

from serve.api.workflow.build_minimal_verification_step import _build_debug_loop_summary, _build_follow_up_queries, _build_module_summary, _build_next_action, _build_residual_risks
from serve.api.workflow.extract import _build_success_criteria, _build_verification_checklist
from serve.api.workflow.locate_bug import plan_fix

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
