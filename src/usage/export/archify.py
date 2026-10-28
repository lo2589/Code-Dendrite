"""cdd archify <file>::<symbol> [root] —— 把一条调用链画成 archify 的交互图。

产物在 <root>/.codedendrite/archify/：<名字>.architecture.json（IR）和 <名字>.html。
本机装了 archify（``npx skills add tt-a1i/archify -g``）就直接渲染并核对源码行号，
没装就只写 IR，并打印渲染命令。
"""
import argparse
import json
import re
import sys
from pathlib import Path

from analyzer.anchors import load_anchors
from usage.export.archify_ir import build_architecture_ir
from usage.export.archify_repo import (
    deliver_command, find_archify, find_node, repository_identity, run_deliver,
)

INSTALL_HINT = "npx skills add tt-a1i/archify -g"


def resolve_anchor(anchors, symbol):
    if symbol in anchors:
        return symbol
    hits = [aid for aid in anchors if aid.endswith("::" + symbol)]
    if len(hits) == 1:
        return hits[0]
    raise SystemExit("找不到唯一的 anchor：{}（候选 {} 个）{}".format(
        symbol, len(hits), "".join("\n  " + h for h in hits[:10])))


def _slug(anchor_id):
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", anchor_id).strip("_")[:120] or "chain"


def _cited_dirty(ir, dirty):
    cited = {s["path"] for c in ir["components"] for s in c.get("sources", [])}
    return sorted(cited & dirty)


def _report_failure(stdout, stderr):
    try:
        receipt = json.loads(stdout)
    except ValueError:
        print((stderr or stdout).strip()[:2000])
        return
    for diag in receipt.get("diagnostics", [])[:12]:
        print("  [{}] {} {}".format(diag.get("code"), json.dumps(diag.get("subject"), ensure_ascii=False),
                                    json.dumps(diag.get("evidence"), ensure_ascii=False)[:200]))
    if not receipt.get("diagnostics"):
        print(json.dumps(receipt, ensure_ascii=False)[:2000])


def main(argv=None):
    p = argparse.ArgumentParser(prog="cdd archify")
    p.add_argument("symbol")
    p.add_argument("directory", nargs="?", default=".")
    p.add_argument("--depth", type=int, default=6)
    p.add_argument("--no-render", action="store_true", help="只写 IR，不调 archify")
    args = p.parse_args(argv)

    root = Path(args.directory).resolve()
    print("[1/4] 读索引 {}".format(root))
    anchors = load_anchors(root=str(root))
    root_id = resolve_anchor(anchors, args.symbol)

    print("[2/4] 读 git 身份（地址 + commit），源码链接钉在这个 commit 上")
    repository, dirty = repository_identity(root)
    name = _slug(root_id)
    ir, stats = build_architecture_ir(anchors, root_id, args.depth, name + ".html", repository)
    print("      chain {}：{} 个函数 · {} 个文件 · {} 条文件间调用".format(
        root_id, stats["functions"], stats["files"], stats["links"]))
    stale = _cited_dirty(ir, dirty)
    if stale:
        print("      注意：这些文件有未提交改动，行号按工作树算，可能和 commit 对不上：")
        for path in stale:
            print("        " + path)

    out_dir = root / ".codedendrite" / "archify"
    out_dir.mkdir(parents=True, exist_ok=True)
    ir_path, html_path = out_dir / (name + ".architecture.json"), out_dir / (name + ".html")
    ir_path.write_text(json.dumps(ir, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[3/4] IR 已写：{}".format(ir_path))

    cli, node = find_archify(), find_node()
    cmd = deliver_command(cli, node, ir_path, html_path, root, repository is not None)
    if args.no_render or not cli or not node:
        if not cli:
            print("[4/4] 本机没有 archify，先装：{}".format(INSTALL_HINT))
        elif not node:
            print("[4/4] 找不到 node（可设 ARCHIFY_NODE）")
        print("      渲染命令：" + " ".join(cmd))
        return 0
    print("[4/4] archify 渲染并核对源码：" + " ".join(cmd))
    code, stdout, stderr = run_deliver(cmd)
    if code != 0:
        print("      archify 没通过：")
        _report_failure(stdout, stderr)
        return code
    print("      完成：{}".format(html_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
