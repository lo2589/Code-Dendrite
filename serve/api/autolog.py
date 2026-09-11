"""
autolog.py — 自动插入 / 撤销调试 log

用法:
  python -m tools.CodeDendrite.api.autolog add <symbol> <target> [--depth N] [--direction down|up|both]
  python -m tools.CodeDendrite.api.autolog remove <target>

插入格式（函数第一行，缩进自动对齐）:
  print("[AUTOLOG] symbol_name")  # marker

撤销: 删除所有含 marker 的行（自动跳过 autolog.py 本身）
注意: 加完 log 后 CD 索引行号失效，撤销后需全量重建。
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

# 用拼接避免 remove 时误删自身源码
MARKER = "# __AUTO" + "LOG__"


def _indent_of(def_line: str) -> str:
    leading = len(def_line) - len(def_line.lstrip(" \t"))
    return " " * (leading + 4)


def _find_def_line(lines: list[str], symbol: str, hint: int) -> int | None:
    """找 def <symbol> 签名结束行（含冒号那行）的行号（1-based）。
    先在 hint ±10 范围内搜 def 行，找不到再全文件搜。
    找到 def 行后向下扫到签名结束的冒号行。
    """
    bare = symbol.split(".")[-1]
    pat = "def {}".format(bare)

    def _scan(start, end):
        for i in range(start, end):
            if pat in lines[i]:
                return i
        return None

    lo, hi = max(0, hint - 11), min(len(lines), hint + 10)
    def_idx = _scan(lo, hi)
    if def_idx is None:
        def_idx = _scan(0, len(lines))
    if def_idx is None:
        return None

    # 向下找签名结束的冒号行（跳过多行签名）
    for i in range(def_idx, min(def_idx + 20, len(lines))):
        stripped = lines[i].rstrip()
        if stripped.endswith(":"):
            return i + 1  # 1-based，插入在冒号行之后

    return def_idx + 1  # 兜底


def _insert_logs_in_file(file_path: str, funcs: list[dict]) -> int:
    """
    funcs: [{symbol, line}]，line 是索引行号提示（1-based，允许偏移）。
    用 _find_def_line 定位真实 def 行，从底往上插避免行号偏移。返回插入数。
    """
    path = Path(file_path)
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
    except Exception as e:
        print("  SKIP {}: {}".format(file_path, e))
        return 0

    resolved = []
    for func in funcs:
        hint = func.get("line") or 1
        real_line = _find_def_line(lines, func["symbol"], hint)
        if real_line is None:
            print("  WARN: def not found for {}".format(func["symbol"]))
            continue
        resolved.append({"symbol": func["symbol"], "line": real_line})

    resolved.sort(key=lambda f: f["line"], reverse=True)
    count = 0
    for func in resolved:
        def_idx = func["line"] - 1
        indent_idx = def_idx
        while indent_idx > 0 and not lines[indent_idx].lstrip().startswith(("def ", "async def ")):
            indent_idx -= 1
        indent = _indent_of(lines[indent_idx])
        log = '{}print("[AUTOLOG] {}")  {}\n'.format(indent, func["symbol"], MARKER)
        lines.insert(def_idx + 1, log)
        count += 1

    path.write_text("".join(lines), encoding="utf-8")
    return count


def cmd_add_file(file_rel: str, target: str) -> None:
    """给单个文件内所有真实函数/方法插 log，不依赖 chain。"""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from serve.api.inspector import list_file_anchors

    funcs = list_file_anchors(file_rel, target)
    if not funcs:
        print("No anchors found in: {}".format(file_rel))
        return

    abs_path = file_rel if Path(file_rel).is_absolute() else str(Path(target) / file_rel)
    funcs_for_insert = [{"symbol": f["symbol"], "line": f["line"]} for f in funcs]

    print("File anchors ({} functions):".format(len(funcs)))
    for f in funcs:
        print("  line={} {} [{}]".format(f["line"], f["symbol"], f["type"]))

    n = _insert_logs_in_file(abs_path, funcs_for_insert)
    print("\n+{} logs -> {}".format(n, abs_path))
    print("Remove: python -m tools.CodeDendrite.api.autolog remove {}".format(target))


def cmd_add_folder(folder_rel: str, target: str) -> None:
    """对文件夹内所有 .py 文件的所有真实函数插 log，不依赖 chain。"""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from serve.api.inspector import list_file_anchors

    folder_abs = Path(folder_rel) if Path(folder_rel).is_absolute() else Path(target) / folder_rel
    _skip = {".codedendrite", "__pycache__", ".git", "node_modules"}
    py_files = []
    for dirpath, dirnames, filenames in os.walk(folder_abs):
        dirnames[:] = [d for d in dirnames if d not in _skip]
        for fname in filenames:
            if fname.endswith(".py"):
                py_files.append(Path(dirpath) / fname)
    py_files = sorted(py_files)

    if not py_files:
        print("No .py files found in: {}".format(folder_abs))
        return

    total = 0
    for py_file in py_files:
        try:
            rel = str(py_file.relative_to(target)).replace("\\", "/")
        except ValueError:
            rel = str(py_file)
        funcs = list_file_anchors(rel, target)
        if not funcs:
            continue
        funcs_for_insert = [{"symbol": f["symbol"], "line": f["line"]} for f in funcs]
        n = _insert_logs_in_file(str(py_file), funcs_for_insert)
        total += n
        print("  +{:3d} logs -> {}".format(n, rel))

    print("\nTotal: {} logs added".format(total))
    print("Remove: python -m tools.CodeDendrite.api.autolog remove {}".format(target))


def cmd_add(symbol: str, target: str, depth: int, direction: str) -> None:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

    from serve.api.inspector import get_downward_chain, get_upward_chain

    chain: list[dict] = []
    seen_syms: set[str] = set()

    if direction in ("down", "both"):
        for entry in get_downward_chain(symbol, target, max_depth=depth):
            if entry["symbol"] not in seen_syms:
                seen_syms.add(entry["symbol"])
                chain.append(entry)

    if direction in ("up", "both"):
        for entry in get_upward_chain(symbol, target, max_depth=depth):
            if entry["symbol"] not in seen_syms:
                seen_syms.add(entry["symbol"])
                chain.append(entry)

    if not chain:
        print("No functions found for: {}".format(symbol))
        return

    print("Chain ({} functions):".format(len(chain)))
    for c in chain:
        print("  [depth={}] {} {}:{}".format(
            c.get("depth", "?"), c["symbol"],
            c.get("file") or "", c.get("line") or ""))

    by_file: dict[str, list[dict]] = defaultdict(list)
    for func in chain:
        if not func.get("file") or not func.get("line"):
            continue
        rel = func["file"]
        abs_path = rel if Path(rel).is_absolute() else str(Path(target) / rel)
        by_file[abs_path].append({"symbol": func["symbol"], "line": func["line"]})

    if not by_file:
        print("No resolvable file paths in chain.")
        return

    total = 0
    for file_path, funcs in by_file.items():
        n = _insert_logs_in_file(file_path, funcs)
        total += n
        print("  +{} logs -> {}".format(n, file_path))

    print("\nTotal: {} logs added across {} files".format(total, len(by_file)))
    print("Remove: python -m tools.CodeDendrite.api.autolog remove {}".format(target))
    print("Note: CD index line numbers are now stale. Rebuild after remove.")


def cmd_remove(target: str) -> None:
    target_path = Path(target)
    this_file = Path(__file__).resolve()
    total = 0
    _skip = {".codedendrite", "__pycache__", ".git", "node_modules"}
    _all_py = []
    for dirpath, dirnames, filenames in os.walk(target_path):
        dirnames[:] = [d for d in dirnames if d not in _skip]
        for fname in filenames:
            if fname.endswith(".py"):
                _all_py.append(Path(dirpath) / fname)
    for py_file in sorted(_all_py):
        if py_file.resolve() == this_file:
            continue
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
            if MARKER not in text:
                continue
            lines = text.splitlines(keepends=True)
            new_lines = [l for l in lines if MARKER not in l]
            removed = len(lines) - len(new_lines)
            if removed:
                py_file.write_text("".join(new_lines), encoding="utf-8")
                total += removed
                print("  -{} lines <- {}".format(removed, py_file))
        except Exception as e:
            print("  ERROR {}: {}".format(py_file, e))

    print("Total removed: {} lines".format(total))
    if total:
        print("Rebuild index: python -m tools.CodeDendrite.api.cli {}".format(target))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="autolog",
        description="自动插入/撤销调试 log（基于 CodeDendrite 链路）",
    )
    sub = parser.add_subparsers(dest="cmd")

    p_add = sub.add_parser("add", help="沿链路插入 log")
    p_add.add_argument("symbol", help="入口函数名")
    p_add.add_argument("target", help="项目根目录（已有 .codedendrite/）")
    p_add.add_argument("--depth", type=int, default=6, help="追链深度（默认 6）")
    p_add.add_argument(
        "--direction", choices=["down", "up", "both"], default="down",
        help="追链方向：down=追 callees，up=追 callers，both=双向（默认 down）",
    )

    p_af = sub.add_parser("add-file", help="给整个文件所有函数插 log（不走 chain）")
    p_af.add_argument("file", help="相对路径，如 shared/provider/service.py")
    p_af.add_argument("target", help="项目根目录")

    p_afd = sub.add_parser("add-folder", help="给整个文件夹所有 .py 所有函数插 log（chain 断时用）")
    p_afd.add_argument("folder", help="相对路径，如 shared/provider")
    p_afd.add_argument("target", help="项目根目录")

    p_rm = sub.add_parser("remove", help="撤销所有 autolog")
    p_rm.add_argument("target", help="项目根目录")

    args = parser.parse_args()

    if args.cmd == "add":
        cmd_add(args.symbol, args.target, args.depth, args.direction)
    elif args.cmd == "add-file":
        cmd_add_file(args.file, args.target)
    elif args.cmd == "add-folder":
        cmd_add_folder(args.folder, args.target)
    elif args.cmd == "remove":
        cmd_remove(args.target)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
