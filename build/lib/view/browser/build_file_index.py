"""
anchor_browser.py - CD Anchor Browser (compound force graph)
=============================================================
  Left   : file tree
  Center : compound graph — class = large rect containing method circles;
           standalone functions = circles; external callers/callees = dashed circles
  Right  : detail panel for selected node

Usage:
  python anchor_browser.py <project_root_with_.codedendrite> [--output browser.html]
"""

import json
import argparse
from pathlib import Path
from collections import defaultdict

from view.browser.dom_sidebar import _HTML

def _build_file_index(anchors: dict) -> dict:
    fa = defaultdict(list)
    for nid in anchors:
        fp = nid.split("::")[0] if "::" in nid else nid
        fa[fp.replace("\\", "/")].append(nid)
    return dict(fa)

def _build_tree(paths: list) -> dict:
    tree = {}
    for fp in sorted(paths):
        parts = fp.replace("\\", "/").split("/")
        node = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                node[part] = None
            else:
                if part not in node or node[part] is None:
                    node[part] = {}
                node = node[part]
    return tree

def _load_anchors(root: str) -> dict:
    p = Path(root) / ".codedendrite" / "anchors.json"
    return json.loads(p.read_text(encoding="utf-8"))

def _read_file_code(root: str, file_anchors: dict) -> dict:
    file_code = {}
    root_path = Path(root)
    for fp in file_anchors:
        src = root_path / fp
        if src.exists():
            try:
                file_code[fp] = src.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass
    return file_code

def _slim(anchor: dict) -> dict:
    def _refs(items: list) -> list[str]:
        refs = []
        for item in items:
            if isinstance(item, str):
                refs.append(item)
            elif isinstance(item, dict):
                target = item.get("target") or item.get("id") or item.get("symbol")
                if target:
                    refs.append(str(target))
        return refs

    # Nothing is cut here any more. The description was clipped at 200
    # characters and each relation list at 15 entries, so an anchor with
    # twenty callers showed fifteen and said nothing about the rest — the
    # page looked complete and was not. Truncating to keep the file small
    # also never worked: the source corpus below is three quarters of it,
    # and the caps only cost information.
    return {
        "t":       anchor.get("symbol_type", ""),
        "desc":    anchor.get("description") or "",
        "callers": _refs(anchor.get("callers", [])),
        "callees": _refs(anchor.get("callees", [])),
        "ins":     anchor.get("inputs", []),
        "outs":    anchor.get("outputs", []),
        "drift":   anchor.get("drift", "ok"),
        "par":     anchor.get("parent_anchor"),
        "vk":      anchor.get("virtual_kind"),
        "ls":      anchor.get("line_start"),
        "le":      anchor.get("line_end"),
    }

def generate(root: str, output: str) -> None:
    """One shell plus one page per file, instead of one page holding everything.

    The single page grew with the repository and nothing else: three quarters
    of it was the source of every file, inlined. At twenty thousand anchors it
    is thirty megabytes, at two hundred thousand it is two hundred and eighty,
    and somewhere in between it stops opening at all. Splitting it puts a bound
    on a page instead of on the project: a file, its source, and the files it
    is connected to.
    """
    from view.module_tree.draw_pages import write_files
    from view.browser.context import _context
    from view.browser.write_page import _write_page, _write_shell

    anchors_path = Path(root) / ".codedendrite" / "anchors.json"
    ctx = _context(root, output)
    for stale in list(ctx["pages_dir"].glob("*.html")) + list(ctx["pages_dir"].glob("*.json")):
        stale.unlink()
    shell = _write_shell(ctx)
    biggest = 0
    for path in ctx["order"]:
        biggest = max(biggest, _write_page(ctx, path))
    write_files(ctx["pages_dir"], ctx["order"])
    print(f"Source:  {anchors_path}  (mtime_ns={anchors_path.stat().st_mtime_ns})")
    print(f"Written: {ctx['out']}  (shell {shell//1024} KB)")
    print(f"         {ctx['pages_dir']}  ({len(ctx['order'])} pages, largest {biggest//1024} KB)")
    print(f"         {len(ctx['anchors'])} anchors, {len(ctx['file_anchors'])} files")

def main() -> None:
    p = argparse.ArgumentParser(description="CD Anchor Browser — compound force graph")
    p.add_argument("root", help="project root containing .codedendrite/")
    # Defaults beside the index it was built from, not into whatever directory
    # the command happened to be run in — a bare relative name dropped a shell
    # and eight thousand page files into the working tree.
    p.add_argument("--output", default=None,
                   help="default: <root>/.codedendrite/anchor_browser.html")
    # One page, checked by content hash and redone only if something it draws
    # moved. This is the path an open takes; the full pass is the idle one.
    p.add_argument("--page", default=None,
                   help="refresh only this page id, if its own inputs changed")
    p.add_argument("--no-index-update", action="store_true",
                   help="with --page: redraw from the index as it stands")
    args = p.parse_args()
    output = args.output or str(Path(args.root) / ".codedendrite" / "anchor_browser.html")
    if args.page is not None:
        from view.browser.write_page import refresh_page
        print(json.dumps(refresh_page(
            args.root, output, args.page,
            update_index=not args.no_index_update), ensure_ascii=False))
        return
    generate(args.root, output)

if __name__ == "__main__":
    main()
