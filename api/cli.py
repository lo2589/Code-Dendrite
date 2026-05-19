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


def _ensure_path():
    api_dir = os.path.dirname(os.path.abspath(__file__))
    codedendrite_root = os.path.dirname(api_dir)
    codedendrite_parent = os.path.dirname(os.path.dirname(codedendrite_root))
    for path in (codedendrite_parent, codedendrite_root):
        if path not in sys.path:
            sys.path.insert(0, path)


_ensure_path()


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


def rebuild(target: str, include_virtual_blocks: bool = True):
    """Rebuild scan results, anchors, and relations from scratch."""
    import time as _time
    _t0 = _time.time()
    from tools.CodeDendrite import (
        scan_project,
        generate_all_anchors,
        generate_relations,
        generate_module_tree,
        generate_module_summary,
    )
    result = scan_project(root=target)
    print("Scan: {} files, {} classes, {} functions  [{:.1f}s]".format(
        result.scanned_files, result.classes_count, result.functions_count, _time.time()-_t0))

    _t1 = _time.time()
    anchors = generate_all_anchors(root=target, include_virtual_blocks=include_virtual_blocks)
    print("Anchors: created {}, skipped {}, failed {}  [{:.1f}s]".format(
        anchors["created"], anchors["skipped"], anchors["failed"], _time.time()-_t1))

    _t2 = _time.time()
    _print_relations(generate_relations(root=target))
    print("Relations done  [{:.1f}s]".format(_time.time()-_t2))

    _t3 = _time.time()
    module_tree = generate_module_tree(root=target)
    print("Module tree: {} modules  hash={}  [{:.1f}s]".format(
        len(module_tree.get("semantic_modules", [])),
        module_tree.get("call_structure_hash", "")[:12], _time.time()-_t3))

    _t4 = _time.time()
    summary = generate_module_summary(root=target)
    print("Summary: {} modules  cache={}  [{:.1f}s]".format(
        len(summary.get("modules", [])),
        "hit" if summary.get("reused_cache") else "miss", _time.time()-_t4))

    print("Wrote results to: {}/.codedendrite/".format(target))

    _t5 = _time.time()
    from tools.CodeDendrite.hash.database import HashDatabase
    from tools.CodeDendrite.api.anchors import load_anchors
    _db = HashDatabase(target)
    _anchors = load_anchors(target)
    _files_with_anchors = list({a.file for a in _anchors.values()})
    _db.update(_files_with_anchors)
    _db.save()
    print("HashDB done  [{:.1f}s]  total [{:.1f}s]".format(_time.time()-_t5, _time.time()-_t0))

    # 2026-05-08: rebuild 后写入所有文件的 hash，供下次 --update 做增量检测。
    # 原来没有这一步，导致 HashDatabase 始终为空，get_stale_files() 永远返回 []。
    # 注意：不用 os.walk 重新扫（会误扫 repos/ 等大目录），直接从已生成的 anchors 提取
    # 涉及的文件路径，只有有 anchor 的文件才需要追踪变化。
    # os.walk 版本（已废弃，太慢）:
    # for _dirpath, _dirnames, _filenames in _os.walk(target): ...
    from tools.CodeDendrite.hash.database import HashDatabase
    from tools.CodeDendrite.api.anchors import load_anchors
    _db = HashDatabase(target)
    _anchors = load_anchors(target)
    _files_with_anchors = list({a.file for a in _anchors.values()})
    _db.update(_files_with_anchors)
    _db.save()


def update(target: str, include_virtual_blocks: bool = True):
    # """Incrementally refresh anchors and relations from git diff."""  # 2026-05-08: 原 docstring
    """Incrementally refresh anchors and relations based on file content hash."""
    codedendrite_dir = os.path.join(target, ".codedendrite")
    required_outputs = (
        os.path.join(codedendrite_dir, "anchors.json"),
        os.path.join(codedendrite_dir, "relations.json"),
    )
    if not all(os.path.exists(path) for path in required_outputs):
        print("Missing CodeDendrite outputs; running full rebuild.")
        rebuild(target, include_virtual_blocks=include_virtual_blocks)
        return

    # 2026-05-08: 改用 HashDatabase.get_stale_files() 检测变更。
    # 原来用 git diff --name-only，只能看到未提交的变更，commit 后就看不到任何变化。
    # HashDatabase 存储每个文件上次 build 时的内容 hash，与 git 状态无关，
    # 无论 checkout / commit / rebase 都能正确检测到实际变化的文件。
    # from tools.CodeDendrite.hash.git_diff import get_changed_files
    # changed = get_changed_files(root=target)
    from tools.CodeDendrite.hash.database import HashDatabase
    from tools.CodeDendrite import (
        on_files_changed,
        generate_relations,
        generate_module_tree,
        generate_module_summary,
    )

    db = HashDatabase(target)
    changed = db.get_stale_files() + db.get_new_files(target)
    if not changed:
        print("No changed files detected; skipping anchor refresh.")
    else:
        print("Changed files: {}".format(len(changed)))
        result = on_files_changed(
            changed_files=changed,
            root=target,
            include_virtual_blocks=include_virtual_blocks,
        )
        print("Anchor update: {}".format(result.get("anchors.updated", result)))

    _print_relations(generate_relations(root=target))
    module_tree = generate_module_tree(root=target)
    print(
        "Module tree: {} modules  hash={}".format(
            len(module_tree.get("semantic_modules", [])),
            module_tree.get("call_structure_hash", "")[:12],
        )
    )
    summary = generate_module_summary(root=target)
    print(
        "Summary: {} modules  cache={}".format(
            len(summary.get("modules", [])),
            "hit" if summary.get("reused_cache") else "miss",
        )
    )
    print("Wrote results to: {}/.codedendrite/".format(target))


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


def _print_debug_loop(result: dict):
    print("Loop stage: {}".format(result.get("loop_stage")))
    top = result.get("top_suspect") or {}
    print("Top suspect: {}".format(top.get("symbol")))
    print("Loop summary: {}".format(result.get("loop_summary")))
    print("Next action: {}".format(result.get("next_action")))
    print("Verification summary: {}".format(result.get("verification_summary")))


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
    from tools.CodeDendrite.api.module_tree import (
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


def module_graph(target: str, include_isolated: bool = True):
    from tools.CodeDendrite.visualize.module_tree_graph import generate_module_tree_graph

    result = generate_module_tree_graph(target, include_isolated=include_isolated)
    print("Module graph:")
    print("  mmd: {}".format(result.get("mmd")))
    print("  md : {}".format(result.get("md")))
    print("  modules: {}".format(result.get("module_count")))
    return result


def anchor_outline(target: str, output: str | None = None):
    from tools.CodeDendrite.api.outline import generate_anchor_outline

    result = generate_anchor_outline(root=target, output=output)
    print("Anchor outline: {}".format(result["output"]))
    print("Anchors: {}  lines: {}".format(result["anchors"], result["lines"]))
    return result


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
    from tools.CodeDendrite.api.workflow import run_debug_loop

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CodeDendrite unified CLI")
    parser.add_argument("target", help="Project root directory")
    parser.add_argument("--update", action="store_true", help="Incrementally refresh anchors and relations")
    parser.add_argument("--debug-loop", action="store_true", help="Run the unified bug-location workflow")
    parser.add_argument("--modules", action="store_true", help="Query semantic modules")
    parser.add_argument("--module-graph", action="store_true", help="Render standard semantic module tree graph")
    parser.add_argument("--anchor-outline", action="store_true", help="Write a folder/file/symbol outline from anchors.json")
    parser.add_argument("--outline-output", help="Output path for --anchor-outline")
    parser.add_argument("--no-virtual-blocks", action="store_true", help="Skip control-flow virtual block anchors")
    parser.add_argument("--no-isolated", action="store_true", help="Hide isolated modules in --module-graph")
    parser.add_argument("--query", help="Free-text module query")
    parser.add_argument("--symbol", help="Find the module that owns this symbol")
    parser.add_argument("--module-id", help="Show one module by id or exact name")
    parser.add_argument("--error", dest="error_msg", help="Error message or failure description")
    parser.add_argument("--file", dest="file_path", help="File related to the failure, e.g. backend/main.py")
    parser.add_argument("--entry-symbol", help="Entry function or method symbol")
    parser.add_argument("--target-symbol", help="Known target function or method symbol")
    parser.add_argument("--conditions", help="Python dict literal for route conditions")
    parser.add_argument("--edited-files", nargs="*", default=None, help="Edited files for verification coverage")
    parser.add_argument("--edited-symbols", nargs="*", default=None, help="Edited symbols for verification coverage")
    parser.add_argument("--no-refresh", action="store_true", help="Skip refresh before debug loop queries")
    parser.add_argument("--limit", type=int, default=5, help="Number of suspect functions to keep")
    parser.add_argument("--module-tree-v2", action="store_true", help="Generate Module Tree V2 (candidates + tree + completeness + html)")
    parser.add_argument("--capability-candidates", action="store_true", help="Generate capability_candidates.json only")
    parser.add_argument("--module-tree-v2-html", action="store_true", help="Render module_tree_v2.html only")
    parser.add_argument("--module-tree-v2-check", action="store_true", help="Show completeness / validation summary")
    parser.add_argument("--path-policy-check", help="Check path role for a given path")
    parser.add_argument("--task-context", help="Generate Task Context Packet for a given anchor/symbol/keyword")
    parser.add_argument("--task-context-compact", help="Print compact text Task Context Packet (for small models)")
    parser.add_argument("--model-profile", choices=["small", "large"], default="small", help="Task context prompt profile")
    args = parser.parse_args(argv)

    target = os.path.abspath(args.target)

    if args.module_tree_v2:
        _cmd_module_tree_v2(target)
        return 0

    if args.capability_candidates:
        _cmd_capability_candidates(target)
        return 0

    if args.module_tree_v2_html:
        _cmd_module_tree_v2_html(target)
        return 0

    if args.module_tree_v2_check:
        _cmd_module_tree_v2_check(target)
        return 0

    if args.path_policy_check:
        _cmd_path_policy_check(target, args.path_policy_check)
        return 0

    if args.task_context:
        _cmd_task_context(target, args.task_context, error_text=args.error_msg, model_profile=args.model_profile)
        return 0

    if args.task_context_compact:
        _cmd_task_context_compact(target, args.task_context_compact, error_text=args.error_msg, model_profile=args.model_profile)
        return 0

    if args.debug_loop:
        if not args.error_msg or not args.file_path:
            parser.error("--debug-loop requires --error and --file")
        debug_loop(
            target=target,
            error_msg=args.error_msg,
            file_path=args.file_path,
            entry_symbol=args.entry_symbol,
            target_symbol=args.target_symbol,
            conditions=_parse_conditions(args.conditions),
            edited_files=args.edited_files,
            edited_symbols=args.edited_symbols,
            refresh=not args.no_refresh,
            limit=args.limit,
        )
        return 0

    if args.modules:
        module_query(
            target=target,
            query=args.query,
            symbol=args.symbol,
            module_id=args.module_id,
            limit=args.limit,
        )
        return 0

    if args.module_graph:
        module_graph(
            target=target,
            include_isolated=not args.no_isolated,
        )
        return 0

    if args.anchor_outline:
        anchor_outline(target, output=args.outline_output)
        return 0

    if args.update:
        update(target, include_virtual_blocks=not args.no_virtual_blocks)
        return 0

    rebuild(target, include_virtual_blocks=not args.no_virtual_blocks)
    return 0


# ── Module Tree V2 CLI 命令 ──────────────────────────────────────

def _cmd_module_tree_v2(target: str):
    from api.path_policy import load_path_policy
    from api.capability_candidates import build_capability_candidates, save_capability_candidates
    from api.module_tree_v2 import generate_module_tree_v2, save_module_tree_v2
    from visualize.module_tree_v2 import generate_module_tree_v2_html

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


def _cmd_capability_candidates(target: str):
    from api.capability_candidates import build_capability_candidates, save_capability_candidates

    result = build_capability_candidates(target)
    path = save_capability_candidates(result, target)
    print("候选数: {}".format(result["summary"]["total_candidates"]))
    print("保存到: {}".format(path))


def _cmd_module_tree_v2_html(target: str):
    from visualize.module_tree_v2 import generate_module_tree_v2_html

    path = generate_module_tree_v2_html(target)
    print("HTML: {}".format(path))


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


def _cmd_path_policy_check(target: str, path: str):
    from api.path_policy import load_path_policy, classify_with_detail

    policy = load_path_policy(target)
    detail = classify_with_detail(path, policy)
    print("路径: {}".format(detail["normalized_path"]))
    print("角色: {}".format(detail["role"]))
    print("规则: {}".format(detail["matched_rule"]))


# ── Task Context Packet CLI 命令 ──────────────────────────────────

def _cmd_task_context(target: str, query: str, error_text: str | None = None, model_profile: str = "small"):
    from api.task_context_packet import generate_task_context, save_task_context

    print("生成 Task Context Packet...")
    print("  查询: {}".format(query))

    ctx = generate_task_context(query, root=target, error_text=error_text, model_profile=model_profile)

    if ctx["resolved_anchor"]:
        print("  定位: {} (匹配 {})".format(ctx["resolved_anchor"], ctx["match_count"]))
    else:
        print("  未找到匹配锚点")
        return

    path = save_task_context(ctx, target)
    est = ctx["token_estimate"]
    print("  token 估算: L0={}, L1={}, L2={}, 总计={}".format(
        est["level0"], est["level1"], est["level2"], est["total"],
    ))
    print("  保存到: {}".format(path))


def _cmd_task_context_compact(target: str, query: str, error_text: str | None = None, model_profile: str = "small"):
    from api.task_context_packet import generate_task_context, format_compact, format_compact_tokens

    ctx = generate_task_context(query, root=target, error_text=error_text, model_profile=model_profile)

    if not ctx["resolved_anchor"]:
        print("未找到匹配锚点: {}".format(query))
        return

    compact = ctx.get("prompt") or format_compact(ctx)
    tokens = ctx.get("token_estimate", {}).get("prompt") or format_compact_tokens(ctx)
    print(compact)
    print("\n--- compact tokens: {} ---".format(tokens))


if __name__ == "__main__":
    raise SystemExit(main())
