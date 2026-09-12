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
import json
import os
import sys
from collections import Counter

from usage.cli.module import _cmd_capability_candidates, _cmd_module_tree_v2, _cmd_module_tree_v2_check, _cmd_module_tree_v2_html, _cmd_path_policy_check, _cmd_task_context, _cmd_task_context_compact, _parse_conditions, _print_relations, anchor_outline, debug_loop, module_graph, module_query

def _ensure_path():
    api_dir = os.path.dirname(os.path.abspath(__file__))
    codedendrite_root = os.path.dirname(api_dir)
    codedendrite_parent = os.path.dirname(os.path.dirname(codedendrite_root))
    for path in (codedendrite_parent, codedendrite_root):
        if path not in sys.path:
            sys.path.insert(0, path)

def rebuild(target: str, include_virtual_blocks: bool = False):
    """Rebuild scan results, anchors, and relations from scratch."""
    import time as _time
    _t0 = _time.time()
    from analyzer.anchors import generate_all_anchors
    from api.relations import generate_relations
    from usage.structure.module_tree import generate_module_summary, generate_module_tree
    from usage.analyze.smart_analyzer.orchestrator import scan_project
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
    from scanner.hashing.database import HashDatabase
    from analyzer.anchors import load_anchors
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
    from scanner.hashing.database import HashDatabase
    from analyzer.anchors import load_anchors
    _db = HashDatabase(target)
    _anchors = load_anchors(target)
    _files_with_anchors = list({a.file for a in _anchors.values()})
    _db.update(_files_with_anchors)
    _db.save()

    # What parser produced this index. Without it every later `update` sees a
    # missing stamp, decides the parser has changed and rebuilds again.
    _dir = os.path.join(target, ".codedendrite")
    os.makedirs(_dir, exist_ok=True)
    with open(os.path.join(_dir, "parser_version.json"), "w", encoding="utf-8") as handle:
        json.dump({"parser": HashDatabase.PARSER_VERSION}, handle)

def update(
    target: str,
    include_virtual_blocks: bool = False,
    exclude_dirs: list | None = None,
    changed_files: list[str] | None = None,
    topology_only: bool = False,
):
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

    # An extractor change invalidates output, not input. Every incremental path
    # asks "has this file changed?" and the answer is no — the file is untouched
    # and the fix is in the parser — so a corrected span never reaches an
    # already-indexed repository. `projectContext` in one repo sat at line
    # 440->440 for a month while a fresh parse gave 470->556. Nothing but a full
    # pass re-derives it, so a version change asks for one.
    # Only when nobody named the files. An explicit list is a caller saying
    # "just these" — that is how one page of `cdd draw` is brought up to date on
    # a click, and it has to stay a handful of files however old the index is.
    if changed_files is not None:
        _skip_parser_check = True
    else:
        _skip_parser_check = False
    from scanner.hashing.database import HashDatabase as _HashDatabase
    _stamp = os.path.join(codedendrite_dir, "parser_version.json")
    _want = None if _skip_parser_check else getattr(_HashDatabase, "PARSER_VERSION", None)
    _have = None
    try:
        with open(_stamp, encoding="utf-8") as handle:
            _have = json.load(handle).get("parser")
    except (OSError, ValueError):
        _have = None
    if not _skip_parser_check and _have != _want:
        print("Parser version {} -> {}; running full rebuild.".format(_have, _want))
        rebuild(target, include_virtual_blocks=include_virtual_blocks)
        os.makedirs(codedendrite_dir, exist_ok=True)
        with open(_stamp, "w", encoding="utf-8") as handle:
            json.dump({"parser": _want}, handle)
        return

    # 2026-05-08: 改用 HashDatabase.get_stale_files() 检测变更。
    # 原来用 git diff --name-only，只能看到未提交的变更，commit 后就看不到任何变化。
    # HashDatabase 存储每个文件上次 build 时的内容 hash，与 git 状态无关，
    # 无论 checkout / commit / rebase 都能正确检测到实际变化的文件。
    # from parse.hash.git_diff import get_changed_files
    # changed = get_changed_files(root=target)
    from scanner.hashing.database import HashDatabase
    from api.relations import generate_relations
    from usage.structure.module_tree import generate_module_summary, generate_module_tree
    from usage.analyze.smart_analyzer.orchestrator import on_files_changed
    from pathlib import Path as _Path

    db = HashDatabase(target)
    if changed_files is None:
        changed = db.get_stale_files() + db.get_new_files(target)
    else:
        root_path = _Path(target).resolve()
        changed = []
        for value in changed_files:
            candidate = _Path(value)
            absolute = candidate.resolve() if candidate.is_absolute() else (root_path / candidate).resolve()
            try:
                relative = absolute.relative_to(root_path).as_posix()
            except ValueError as exc:
                raise SystemExit("Changed file escapes project root: {}".format(value)) from exc
            if relative not in changed:
                changed.append(relative)
    if exclude_dirs:
        _excl = set(exclude_dirs)
        changed = [f for f in changed if not any(part in _excl for part in _Path(f).parts)]
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
    if not topology_only:
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

    from analyzer.anchors import load_anchors
    _anchors = load_anchors(target)
    _files_with_anchors = list({a.file for a in _anchors.values()} | set(changed))
    refreshed = db.update(_files_with_anchors)
    print("HashDB refreshed: {} files".format(refreshed))
    print("Wrote results to: {}/.codedendrite/".format(target))

def external_deps(target: str, show_files: bool = False) -> int:
    """Report the packages that must be installed before the project imports."""
    _ensure_path()
    import json
    from pathlib import Path

    from scanner.project.deps import external_dependencies, format_report

    database_path = Path(target).expanduser().resolve() / ".code_genome_db.json"
    if not database_path.is_file():
        print(f"missing {database_path} — run the CLI once without --deps to build it")
        return 1

    with open(database_path, encoding="utf-8") as handle:
        database = json.load(handle)
    print(format_report(external_dependencies(database, target), show_files=show_files))
    return 0

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CodeDendrite unified CLI")
    parser.add_argument("target", help="Project root directory")
    parser.add_argument("--update", action="store_true", help="Incrementally refresh anchors and relations")
    parser.add_argument("--changed-files", nargs="*", default=None, help="Refresh only these project-relative files")
    parser.add_argument("--topology-only", action="store_true", help="Skip module tree and summary refresh")
    parser.add_argument("--debug-loop", action="store_true", help="Run the unified bug-location workflow")
    parser.add_argument("--modules", action="store_true", help="Query semantic modules")
    parser.add_argument("--module-graph", action="store_true", help="Render standard semantic module tree graph")
    parser.add_argument("--deps", action="store_true", help="List external packages the project imports")
    parser.add_argument("--deps-files", action="store_true", help="With --deps, show which files import each package")
    parser.add_argument("--anchor-outline", action="store_true", help="Write a folder/file/symbol outline from anchors.json")
    parser.add_argument("--outline-output", help="Output path for --anchor-outline")
    parser.add_argument("--virtual-blocks", action="store_true", help="Include debug-only control-flow virtual block anchors")
    parser.add_argument("--no-virtual-blocks", action="store_true", help="Deprecated compatibility flag; virtual blocks are off by default")
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

    if args.deps:
        return external_deps(target, show_files=args.deps_files)

    if args.anchor_outline:
        anchor_outline(target, output=args.outline_output)
        return 0

    include_virtual_blocks = bool(args.virtual_blocks and not args.no_virtual_blocks)

    if args.update:
        update(
            target,
            include_virtual_blocks=include_virtual_blocks,
            changed_files=args.changed_files,
            topology_only=args.topology_only,
        )
        return 0

    rebuild(target, include_virtual_blocks=include_virtual_blocks)
    return 0

_ensure_path()
if __name__ == "__main__":
    raise SystemExit(main())
