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

def _extract_error_line(error_msg: str) -> Optional[int]:
    match = re.search(r"line (\d+)", error_msg or "")
    return int(match.group(1)) if match else None

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

def _get_anchor_from_suspect(suspect: dict, anchors: dict):
    symbol = suspect.get("symbol")
    file_path = suspect.get("file")
    for anchor in anchors.values():
        if anchor.symbol != symbol:
            continue
        if anchor.file == file_path or anchor.file.endswith(file_path):
            return anchor
    return None

def _module_name_from_file(file_path: str) -> str:
    stem = Path(file_path).stem
    parts = [part for part in stem.split("_") if part]
    return "_".join(parts[:3]) if parts else stem

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
        from usage.structure.module_tree import (
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

    # File+line localization only needs anchors.json.  Old/snapshot indexes may
    # intentionally omit module_tree.json; module enrichment must not make the
    # primary localization command fail.
    try:
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
    except (FileNotFoundError, KeyError, ValueError):
        pass

    candidates.sort(key=lambda item: (-item["score"], item["name"] or ""))
    return candidates[:limit]
