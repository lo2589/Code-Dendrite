from __future__ import annotations

"""
CodeDendrite command-line entry point.

Examples:
    python api/cli.py D:\repo
    python api/cli.py D:\repo --update
    python api/cli.py D:\repo --debug-loop --file backend/main.py --error "..."
"""
import argparse
import ast
import os
import sys
from collections import Counter

def _cmd_capability_candidates(target: str):
    from synth.api.capability_candidates import build_capability_candidates, save_capability_candidates

    result = build_capability_candidates(target)
    path = save_capability_candidates(result, target)
    print("候选数: {}".format(result["summary"]["total_candidates"]))
    print("保存到: {}".format(path))

def _cmd_module_tree_v2(target: str):
    from synth.api.path_policy import load_path_policy
    from synth.api.capability_candidates import build_capability_candidates, save_capability_candidates
    from synth.api.module_tree_v2 import generate_module_tree_v2, save_module_tree_v2
    from view.visualize.module_tree_v2 import generate_module_tree_v2_html

    print("[1/4] 加载路径策略...")
    policy = load_path_policy(target)

    print("[2/4] 生成能力候选...")
    candidates = build_capability_candidates(target, policy=policy)
    save_capability_candidates(candidates, target)
    print("  候选数: {}".format(candidates["summary"]["total_candidates"]))

    print("[3/4] 生成模块树 V2...")
    tree = generate_module_tree_v2(target, policy=policy, candidates=candidates)
    tp, cp = save_module_tree_v2(tree, target)
    print("  模块数: {}  边数: {}".format(
        tree["summary"]["total_modules"], len(tree["edges"])))

    print("[4/4] 渲染 HTML...")
    html_path = generate_module_tree_v2_html(target)
    print("  HTML: {}".format(html_path))

    print("\n完成! 输出目录: {}/.codedendrite/".format(target))

def _cmd_module_tree_v2_check(target: str):
    import json
    from pathlib import Path

    comp_path = Path(target) / ".codedendrite" / "module_tree_v2_completeness.json"
    tree_path = Path(target) / ".codedendrite" / "module_tree_v2.json"

    if not tree_path.exists():
        print("module_tree_v2.json 不存在，先运行 --module-tree-v2")
        return

    with open(tree_path, encoding="utf-8") as f:
        tree = json.load(f)

    summary = tree.get("summary", {})
    comp = tree.get("completeness", {})

    print("=== Module Tree V2 检查 ===")
    print("模块数: {}".format(summary.get("total_modules", 0)))
    print("状态: {}".format(summary.get("by_status", {})))
    print("信心: {}".format(summary.get("by_confidence", {})))

    ac = comp.get("area_coverage", {})
    print("\n区域覆盖: {}/{}".format(ac.get("covered", 0), ac.get("total_areas", 0)))
    if ac.get("uncovered"):
        print("  未覆盖: {}".format(", ".join(ac["uncovered"])))

    warnings = comp.get("fake_module_warnings", [])
    if warnings:
        print("\n假模块警告:")
        for w in warnings:
            print("  - {} ({})".format(w.get("name"), w.get("reason")))

    low_conf = comp.get("low_confidence_modules", [])
    if low_conf:
        print("\n低信心模块:")
        for lc in low_conf:
            print("  - {} ({})".format(lc.get("name"), lc.get("confidence")))

    missing = comp.get("missing_evidence", [])
    if missing:
        print("\n证据不足:")
        for me in missing:
            print("  - {} (缺 {})".format(me.get("name"), ", ".join(me.get("missing", []))))

    if not warnings and not low_conf and not missing:
        print("\n所有检查通过!")

def _cmd_module_tree_v2_html(target: str):
    from view.visualize.module_tree_v2 import generate_module_tree_v2_html

    path = generate_module_tree_v2_html(target)
    print("HTML: {}".format(path))

def _cmd_path_policy_check(target: str, path: str):
    from synth.api.path_policy import load_path_policy, classify_with_detail

    policy = load_path_policy(target)
    detail = classify_with_detail(path, policy)
    print("路径: {}".format(detail["normalized_path"]))
    print("角色: {}".format(detail["role"]))
    print("规则: {}".format(detail["matched_rule"]))

def _cmd_task_context(target: str, query: str, error_text: str | None = None, model_profile: str = "small"):
    from synth.api.task_context_packet import generate_task_context, save_task_context

    print("生成 Task Context Packet...")
    print("  查询: {}".format(query))

    ctx = generate_task_context(query, root=target, error_text=error_text, model_profile=model_profile)

    navigation = ctx.get("navigation") or {}
    if ctx["resolved_anchor"]:
        print("  定位: {} (匹配 {})".format(ctx["resolved_anchor"], ctx["match_count"]))
    elif navigation.get("status") == "ambiguous":
        print("  歧义: {} 个匹配，未生成导航命令".format(ctx["match_count"]))
        for row in ctx.get("ambiguous_matches", [])[:5]:
            print("    - {}:{} {}".format(
                row.get("file", ""), row.get("line", ""), row.get("anchor", ""),
            ))
    else:
        print("  未找到匹配锚点")

    path = save_task_context(ctx, target)
    est = ctx["token_estimate"]
    print("  token 估算: L0={}, L1={}, L2={}, 总计={}".format(
        est["level0"], est["level1"], est["level2"], est["total"],
    ))
    print("  保存到: {}".format(path))

def _cmd_task_context_compact(target: str, query: str, error_text: str | None = None, model_profile: str = "small"):
    from synth.api.task_context_packet import generate_task_context, format_compact, format_compact_tokens

    ctx = generate_task_context(query, root=target, error_text=error_text, model_profile=model_profile)

    compact = ctx.get("prompt") or format_compact(ctx)
    tokens = ctx.get("token_estimate", {}).get("prompt") or format_compact_tokens(ctx)
    print(compact)
    print("\n--- compact tokens: {} ---".format(tokens))

def _print_debug_loop(result: dict):
    print("Loop stage: {}".format(result.get("loop_stage")))
    top = result.get("top_suspect") or {}
    print("Top suspect: {}".format(top.get("symbol")))
    print("Loop summary: {}".format(result.get("loop_summary")))
    print("Next action: {}".format(result.get("next_action")))
    print("Verification summary: {}".format(result.get("verification_summary")))

def debug_loop(
    target: str,
    error_msg: str,
    file_path: str,
    entry_symbol: str | None = None,
    target_symbol: str | None = None,
    conditions: dict | None = None,
    edited_files: list[str] | None = None,
    edited_symbols: list[str] | None = None,
    refresh: bool = True,
    limit: int = 5,
):
    from serve.api.workflow import run_debug_loop

    result = run_debug_loop(
        error_msg=error_msg,
        file_path=file_path,
        root=target,
        entry_symbol=entry_symbol,
        target_symbol=target_symbol,
        conditions=conditions or {},
        edited_files=edited_files or [],
        edited_symbols=edited_symbols or [],
        refresh=refresh,
        limit=limit,
    )
    _print_debug_loop(result)
    return result

def _print_relations(relations):
    total = relations.get("total", 0)
    types = relations.get("by_type", {})
    print(
        "Relations: {} edges  call={} inherit={} dataflow={} impact={} dispatch={}".format(
            total,
            types.get("call", 0),
            types.get("inherit", 0),
            types.get("dataflow", 0),
            types.get("impact", 0),
            types.get("dispatch", 0),
        )
    )

def module_graph(target: str, include_isolated: bool = True):
    from view.visualize.module_tree_graph import generate_module_tree_graph

    result = generate_module_tree_graph(target, include_isolated=include_isolated)
    print("Module graph:")
    print("  mmd: {}".format(result.get("mmd")))
    print("  md : {}".format(result.get("md")))
    print("  modules: {}".format(result.get("module_count")))
    return result

def _parse_conditions(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        value = ast.literal_eval(raw)
    except Exception as exc:
        raise SystemExit("Failed to parse --conditions: {}".format(exc)) from exc
    if not isinstance(value, dict):
        raise SystemExit("--conditions must evaluate to a dict, e.g. \"{'method': 'chat_message'}\"")
    return value

def anchor_outline(target: str, output: str | None = None):
    from serve.api.outline import generate_anchor_outline

    result = generate_anchor_outline(root=target, output=output)
    print("Anchor outline: {}".format(result["output"]))
    print("Anchors: {}  lines: {}".format(result["anchors"], result["lines"]))
    return result

def _print_module(module: dict) -> None:
    print("Module: {} ({})".format(module.get("name"), module.get("id")))
    responsibility = module.get("responsibility") or module.get("responsibility_hint")
    if responsibility:
        print("Responsibility: {}".format(responsibility))
    entries = [
        item.get("symbol_id", "")
        for item in module.get("entry_functions", [])
        if item.get("symbol_id")
    ]
    if entries:
        print("Entries:")
        for item in entries[:5]:
            print("  - {}".format(item))
    members = module.get("member_symbols", [])
    if members:
        print("Members:")
        for item in members[:8]:
            print("  - {}".format(item))

def module_query(
    target: str,
    query: str | None = None,
    symbol: str | None = None,
    module_id: str | None = None,
    limit: int = 5,
):
    from synth.api.module_tree import (
        find_module_for_symbol,
        get_module,
        query_modules,
    )

    if module_id:
        module = get_module(module_id, root=target)
        if not module:
            raise SystemExit("Module not found: {}".format(module_id))
        _print_module(module)
        return [module]

    if symbol:
        module = find_module_for_symbol(symbol, root=target)
        if not module:
            raise SystemExit("No module matched symbol: {}".format(symbol))
        _print_module(module)
        return [module]

    if not query:
        raise SystemExit("module query requires --query, --symbol, or --module-id")

    modules = query_modules(query, root=target, limit=limit)
    if not modules:
        print("No modules matched query: {}".format(query))
        return []
    for index, module in enumerate(modules, 1):
        print("[{}] {} ({})".format(index, module.get("name"), module.get("id")))
        responsibility = module.get("responsibility") or module.get("responsibility_hint")
        if responsibility:
            print("    {}".format(responsibility))
    return modules
