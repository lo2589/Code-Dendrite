"""cdd archify <file>::<symbol> [root] —— 把一条调用链画成 archify 的交互图。

产物在 <root>/.codedendrite/archify/：<名字>.architecture.json（IR）和 <名字>.html。
本机装了 archify（``npx skills add tt-a1i/archify -g``）就直接渲染并核对源码行号，
没装就只写 IR，并打印渲染命令。

archify 拒绝版面时（边穿过节点、图太宽……），多半是链太大、一张图读不了：自动把深度
减一重画，直到通过，并说清楚实际画到了哪一层。
"""
import argparse
import json
import re
import sys
from pathlib import Path

from analyzer.anchors import load_anchors
from usage.export.archify_ir import build_architecture_ir
from usage.export.archify_repair import polish
from usage.export.archify_repo import (
    deliver_command, find_archify, find_node, read_layout, repository_identity, run_deliver,
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


def _diagnostics(stdout):
    try:
        return json.loads(stdout).get("diagnostics", [])
    except ValueError:
        return []


def _report_failure(stdout, stderr):
    diags = _diagnostics(stdout)
    if not diags:
        print((stderr or stdout).strip()[:2000])
    for diag in diags[:12]:
        print("  [{}] {}".format(diag.get("code"), (diag.get("message") or "")[:300]))
        if diag.get("evidence"):
            print("      evidence: " + json.dumps(diag["evidence"], ensure_ascii=False)[:200])
        if diag.get("supportedFixes"):
            print("      fixes: " + ", ".join(diag["supportedFixes"]))


def _write_ir(anchors, root_id, depth, name, repository, out_dir):
    ir, stats = build_architecture_ir(anchors, root_id, depth, name + ".html", repository)
    ir_path = out_dir / (name + ".architecture.json")
    ir_path.write_text(json.dumps(ir, ensure_ascii=False, indent=2), encoding="utf-8")
    return ir, stats, ir_path


def _polish(ir, ir_path, cli, node, root, with_repo):
    """archify 合法 ≠ 读得懂：查并线和挂错的标签，一次试一个改法（见 archify_repair）。
    胜出的那一版写回 ir_path，返回还剩的问题。"""
    trial_path = ir_path.with_name(ir_path.stem + ".trial.json")

    def validate(candidate):
        trial_path.write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")
        return read_layout(cli, node, trial_path, root, with_repo)

    try:
        best, remaining = polish(ir, validate)
    finally:
        trial_path.unlink(missing_ok=True)
    ir_path.write_text(json.dumps(best, ensure_ascii=False, indent=2), encoding="utf-8")
    return remaining


def _summary(stats):
    return "{} 个函数 · {} 个文件 · {} 条文件间调用".format(stats["functions"], stats["files"], stats["links"])


def _render(anchors, root_id, args, name, repository, out_dir, cli, node, root):
    """从 --depth 往下逐层试，返回 archify 的退出码。"""
    html_path = out_dir / (name + ".html")
    last = None
    for depth in range(args.depth, 0, -1):
        ir, stats, ir_path = _write_ir(anchors, root_id, depth, name, repository, out_dir)
        remaining = _polish(ir, ir_path, cli, node, root, repository is not None)
        cmd = deliver_command(cli, node, ir_path, html_path, root, repository is not None)
        code, stdout, stderr = run_deliver(cmd)
        if code == 0:
            if depth < args.depth:
                print("      深度 {} 太大，archify 不接受；实际画到深度 {}（{}）".format(args.depth, depth, _summary(stats)))
            for line in remaining:
                print("      仍可能认错：" + line)
            print("      完成：{}".format(html_path))
            return 0
        last = (code, stdout, stderr)
        print("      深度 {}（{}）没通过：{} 条版面问题，减一层再画".format(depth, _summary(stats), len(_diagnostics(stdout)) or "?"))
    print("      archify 没通过：")
    _report_failure(last[1], last[2])
    return last[0]


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
    out_dir = root / ".codedendrite" / "archify"
    out_dir.mkdir(parents=True, exist_ok=True)
    ir, stats, ir_path = _write_ir(anchors, root_id, args.depth, name, repository, out_dir)
    print("      chain {}：{}".format(root_id, _summary(stats)))
    stale = _cited_dirty(ir, dirty)
    if stale:
        print("      注意：这些文件有未提交改动，行号按工作树算，可能和 commit 对不上：")
        for path in stale:
            print("        " + path)
    print("[3/4] IR 已写：{}".format(ir_path))

    cli, node = find_archify(), find_node()
    if args.no_render or not cli or not node:
        if not cli:
            print("[4/4] 本机没有 archify，先装：{}".format(INSTALL_HINT))
        elif not node:
            print("[4/4] 找不到 node（可设 ARCHIFY_NODE）")
        cmd = deliver_command(cli, node, ir_path, out_dir / (name + ".html"), root, repository is not None)
        print("      渲染命令：" + " ".join(cmd))
        return 0
    print("[4/4] archify 渲染并核对源码")
    return _render(anchors, root_id, args, name, repository, out_dir, cli, node, root)


if __name__ == "__main__":
    sys.exit(main())
