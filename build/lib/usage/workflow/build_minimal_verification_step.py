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

def _align_modules_with_suspects(
    related_modules: list[dict],
    suspects: list[dict],
    root: str,
) -> list[dict]:
    try:
        from usage.structure.module_tree import find_module_for_symbol
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
        try:
            module = find_module_for_symbol(symbol, root=root)
            boost(module, f"suspect:{symbol}", 6 - index)
            if file_path:
                module = find_module_for_symbol(f"{file_path}::{symbol}", root=root)
                boost(module, f"suspect-id:{symbol}", 8 - index)
        except (FileNotFoundError, KeyError, ValueError):
            return related_modules

    aligned = list(by_id.values())
    aligned.sort(key=lambda item: (-item.get("score", 0), item.get("name") or ""))
    return aligned

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
            "type": "need_evidence",
            "message": (
                "No function-level evidence is strong enough to recommend an edit. "
                "Provide an error line, full target symbol, entry symbol, or reproducible trace."
            ),
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
