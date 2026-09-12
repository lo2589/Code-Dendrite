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

from usage.workflow.build_minimal_verification_step import _align_modules_with_suspects, _build_debug_loop_summary, _build_edit_scope, _build_edit_targets, _build_fix_hypothesis, _build_follow_up_queries, _build_minimal_verification_step, _build_module_summary, _build_next_action, _build_proposed_steps, _build_residual_risks, _build_risk_notes
from usage.workflow.extract import _build_success_criteria, _build_verification_checklist, _build_verification_steps, _extract_error_line, _extract_module_query_terms, _extract_relevant_branches, _extract_relevant_variables, _get_anchor_from_suspect, _module_name_from_file, _locate_relevant_modules
from usage.workflow.resolve_target_anchor import _rank_bug_suspects, _refresh_navigation, _resolve_target_anchor, _trace_bug_path, debug_workflow
from usage.workflow.locate_bug import locate_bug, diagnose_bug, plan_fix
from usage.workflow.run_debug_loop import verify_fix, run_debug_loop

__all__ = ['_align_modules_with_suspects', '_build_debug_loop_summary', '_build_edit_scope', '_build_edit_targets', '_build_fix_hypothesis', '_build_follow_up_queries', '_build_minimal_verification_step', '_build_module_summary', '_build_next_action', '_build_proposed_steps', '_build_residual_risks', '_build_risk_notes', '_build_success_criteria', '_build_verification_checklist', '_build_verification_steps', '_extract_error_line', '_extract_module_query_terms', '_extract_relevant_branches', '_extract_relevant_variables', '_get_anchor_from_suspect', '_module_name_from_file', '_locate_relevant_modules', '_rank_bug_suspects', '_refresh_navigation', '_resolve_target_anchor', '_trace_bug_path', 'debug_workflow', 'locate_bug', 'diagnose_bug', 'plan_fix', 'verify_fix', 'run_debug_loop']
