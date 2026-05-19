"""
trace_cli.py — 动态分析 CLI 入口

命令：
  trace   --project <root> --script xxx.py [-- arg1 arg2]
  edges   --project <root>
  routes  --project <root>
  merge   --project <root> --relations <relations.json>

不影响现有 CLI（api/cli.py），独立模块。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .dynamic_store import (
    iter_trace_events,
    save_executed_edges,
    load_executed_edges,
    save_routes,
)
from .trace_runner import run_with_trace
from .edge_extractor import extract_executed_edges
from .route_mapper import extract_dispatch_routes
from .merge import merge_static_with_executed


def cmd_trace(args: argparse.Namespace) -> None:
    """执行带 trace 的脚本。"""
    print(f"[dynamic] Tracing: {args.script}")
    print(f"[dynamic] Project: {args.project}")

    run_with_trace(
        project_root=args.project,
        script_path=args.script,
        script_args=args.script_args,
        clear_old=not args.append,
    )

    print("[dynamic] Trace complete. Events written to trace_events.jsonl")


def cmd_edges(args: argparse.Namespace) -> None:
    """从 trace 事件提取执行边。"""
    events = list(iter_trace_events(args.project))
    if not events:
        print("[dynamic] No trace events found. Run 'trace' first.")
        return

    edges = extract_executed_edges(events)
    filepath = save_executed_edges(args.project, edges)
    print(f"[dynamic] Extracted {len(edges)} edges → {filepath}")

    # 打印 top 10
    for e in edges[:10]:
        print(f"  {e['src']} → {e['dst']}  (×{e['count']})")


def cmd_routes(args: argparse.Namespace) -> None:
    """从执行边提取路由映射。"""
    edges = load_executed_edges(args.project)
    if not edges:
        print("[dynamic] No executed edges found. Run 'edges' first.")
        return

    routes = extract_dispatch_routes(edges)
    filepath = save_routes(args.project, routes)

    total_targets = sum(len(r["targets"]) for r in routes["dispatch_routes"])
    print(f"[dynamic] Found {len(routes['dispatch_routes'])} dispatchers, "
          f"{total_targets} route targets → {filepath}")

    for r in routes["dispatch_routes"]:
        print(f"  {r['dispatcher']}:")
        for t in r["targets"]:
            print(f"    → {t}")


def cmd_merge(args: argparse.Namespace) -> None:
    """将动态数据融合到静态关系图（只读，输出到 stdout 或文件）。"""
    # 加载静态关系
    rel_path = Path(args.relations)
    if not rel_path.exists():
        print(f"[dynamic] Relations file not found: {rel_path}", file=sys.stderr)
        sys.exit(1)

    with open(rel_path, "r", encoding="utf-8", errors="replace") as f:
        relations = json.load(f)

    edges_list = relations if isinstance(relations, list) else relations.get("edges", [])

    # 加载动态边
    executed = load_executed_edges(args.project)
    if not executed:
        print("[dynamic] No executed edges. Run 'edges' first.", file=sys.stderr)
        sys.exit(1)

    enriched = merge_static_with_executed(edges_list, executed)
    print(f"[dynamic] Enriched {len(enriched)} static edges with dynamic data")

    if args.output:
        out_path = Path(args.output)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(enriched, f, ensure_ascii=False, indent=2)
        print(f"[dynamic] Written to {out_path}")
    else:
        print(json.dumps(enriched[:5], ensure_ascii=False, indent=2))
        if len(enriched) > 5:
            print(f"  ... ({len(enriched)} total)")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="codedendrite-dynamic",
        description="CodeDendrite Dynamic Analysis",
    )
    sub = parser.add_subparsers(dest="command")

    # trace
    p_trace = sub.add_parser("trace", help="Run a script with call tracing")
    p_trace.add_argument("--project", required=True, help="Project root path")
    p_trace.add_argument("--script", required=True, help="Python script to trace")
    p_trace.add_argument("--append", action="store_true", help="Append to existing trace")
    p_trace.add_argument("script_args", nargs="*", help="Args for the script")

    # edges
    p_edges = sub.add_parser("edges", help="Extract executed edges from trace")
    p_edges.add_argument("--project", required=True, help="Project root path")

    # routes
    p_routes = sub.add_parser("routes", help="Extract dispatch routes from edges")
    p_routes.add_argument("--project", required=True, help="Project root path")

    # merge
    p_merge = sub.add_parser("merge", help="Merge dynamic data with static relations")
    p_merge.add_argument("--project", required=True, help="Project root path")
    p_merge.add_argument("--relations", required=True, help="Path to relations.json")
    p_merge.add_argument("--output", help="Output file (default: stdout preview)")

    args = parser.parse_args(argv)

    if args.command == "trace":
        cmd_trace(args)
    elif args.command == "edges":
        cmd_edges(args)
    elif args.command == "routes":
        cmd_routes(args)
    elif args.command == "merge":
        cmd_merge(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
