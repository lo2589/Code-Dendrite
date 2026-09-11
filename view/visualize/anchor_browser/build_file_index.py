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

from view.visualize.anchor_browser.dom_sidebar import _HTML

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

    return {
        "t":       anchor.get("symbol_type", ""),
        "desc":    (anchor.get("description") or "")[:200],
        "callers": _refs(anchor.get("callers", []))[:15],
        "callees": _refs(anchor.get("callees", []))[:15],
        "ins":     anchor.get("inputs", []),
        "outs":    anchor.get("outputs", []),
        "drift":   anchor.get("drift", "ok"),
        "par":     anchor.get("parent_anchor"),
        "vk":      anchor.get("virtual_kind"),
        "ls":      anchor.get("line_start"),
        "le":      anchor.get("line_end"),
    }

def generate(root: str, output: str) -> None:
    anchors_path = Path(root) / ".codedendrite" / "anchors.json"
    anchors = _load_anchors(root)
    file_anchors = _build_file_index(anchors)
    tree = _build_tree(list(file_anchors.keys()))
    slim = {nid: _slim(a) for nid, a in anchors.items()}
    file_code = _read_file_code(root, file_anchors)

    def _js(obj):
        return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")

    data_js = (
        "const ANCHORS = "      + _js(slim)         + ";\n"
        "const FILE_ANCHORS = " + _js(file_anchors) + ";\n"
        "const FILE_TREE = "    + _js(tree)         + ";\n"
    )
    file_code_js = "const FILE_CODE = " + _js(file_code) + ";\n"

    html = (_HTML
            .replace("__DATA_JS__", data_js)
            .replace("__FILE_CODE_JS__", file_code_js)
            .replace("__PROJECT__", Path(root).name))
    out = Path(output)
    out.write_text(html, encoding="utf-8")
    code_kb = sum(len(v) for v in file_code.values()) // 1024
    print(f"Source:  {anchors_path}  (mtime_ns={anchors_path.stat().st_mtime_ns})")
    print(f"Written: {out}  ({len(html)//1024} KB,  {len(anchors)} anchors,  {len(file_anchors)} files,  {code_kb} KB source)")

def main() -> None:
    p = argparse.ArgumentParser(description="CD Anchor Browser — compound force graph")
    p.add_argument("root", help="project root containing .codedendrite/")
    p.add_argument("--output", default="anchor_browser.html")
    args = p.parse_args()
    generate(args.root, args.output)

if __name__ == "__main__":
    main()
