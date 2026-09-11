"""
module_tree_graph.py - Standard semantic module tree renderer
==============================================================

Input schema:
  <root>/.codedendrite/module_tree.json
  - semantic_modules[*]
    - id
    - name
    - responsibility / responsibility_hint
    - entry_functions[*].symbol_id
    - cross_module_edges[*].to_module / edge_type / count

Output:
  - <root>/.codedendrite/module_tree_graph.mmd
  - <root>/.codedendrite/module_tree_graph.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List


def _load_module_tree(root: str) -> dict:
    path = Path(root) / ".codedendrite" / "module_tree.json"
    if not path.exists():
        raise FileNotFoundError(f"module_tree.json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_id(module_id: str) -> str:
    return "m_" + "".join(ch if ch.isalnum() else "_" for ch in module_id)


def _entry_preview(module: dict, limit: int = 2) -> str:
    entries = []
    for item in module.get("entry_functions", []):
        symbol_id = item.get("symbol_id", "")
        if symbol_id:
            entries.append(symbol_id.split("::")[-1])
    if not entries:
        return "-"
    return " / ".join(entries[:limit])


def _module_label(module: dict) -> str:
    name = module.get("name") or module.get("id", "module")
    mid = module.get("id", "")
    entry = _entry_preview(module, limit=2)
    return f"{name}\\n({mid})\\nentry: {entry}"


def _sorted_modules(data: dict) -> List[dict]:
    modules = list(data.get("semantic_modules", []))
    modules.sort(key=lambda m: (m.get("id", ""), m.get("name", "")))
    return modules


def build_mermaid(data: dict, include_isolated: bool = True) -> str:
    modules = _sorted_modules(data)
    by_id: Dict[str, dict] = {m.get("id", ""): m for m in modules if m.get("id")}

    edge_lines = []
    connected_ids = set()
    for mod in modules:
        src_id = mod.get("id", "")
        if not src_id:
            continue
        for edge in mod.get("cross_module_edges", []):
            dst_id = edge.get("to_module", "")
            if dst_id not in by_id:
                continue
            etype = edge.get("edge_type", "?")
            cnt = edge.get("count", 0)
            edge_lines.append(
                f"  {_safe_id(src_id)} -->|{etype}:{cnt}| {_safe_id(dst_id)}"
            )
            connected_ids.add(src_id)
            connected_ids.add(dst_id)

    lines = ["graph TD"]
    for mod in modules:
        mid = mod.get("id", "")
        if not mid:
            continue
        if not include_isolated and mid not in connected_ids:
            continue
        lines.append(f'  {_safe_id(mid)}["{_module_label(mod)}"]')

    if edge_lines:
        lines.extend(edge_lines)
    else:
        lines.append('  note["No cross-module edges"]')

    return "\n".join(lines) + "\n"


def build_markdown(data: dict, mermaid: str) -> str:
    modules = _sorted_modules(data)
    lines = [
        "# Module Tree Graph (Standard)",
        "",
        "Input: `.codedendrite/module_tree.json`",
        "",
        "## Modules",
        "",
        "| id | name | entry preview | responsibility |",
        "|---|---|---|---|",
    ]
    for mod in modules:
        mid = mod.get("id", "")
        name = mod.get("name", "")
        entry = _entry_preview(mod, limit=3)
        responsibility = mod.get("responsibility") or mod.get("responsibility_hint") or "-"
        lines.append(f"| `{mid}` | `{name}` | `{entry}` | {responsibility} |")

    lines.extend(
        [
            "",
            "## Graph",
            "",
            "```mermaid",
            mermaid.rstrip(),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def generate_module_tree_graph(root: str, include_isolated: bool = True) -> dict:
    data = _load_module_tree(root)
    mermaid = build_mermaid(data, include_isolated=include_isolated)
    markdown = build_markdown(data, mermaid)

    out_dir = Path(root) / ".codedendrite"
    out_dir.mkdir(parents=True, exist_ok=True)
    mmd_path = out_dir / "module_tree_graph.mmd"
    md_path = out_dir / "module_tree_graph.md"
    mmd_path.write_text(mermaid, encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")

    return {
        "mmd": str(mmd_path),
        "md": str(md_path),
        "module_count": len(data.get("semantic_modules", [])),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Render standard semantic module tree graph")
    parser.add_argument("root", help="Project root directory")
    parser.add_argument(
        "--no-isolated",
        action="store_true",
        help="Hide isolated modules with no cross_module_edges",
    )
    args = parser.parse_args()

    result = generate_module_tree_graph(
        root=args.root,
        include_isolated=not args.no_isolated,
    )
    print(f"module_tree_graph.mmd: {result['mmd']}")
    print(f"module_tree_graph.md : {result['md']}")
    print(f"modules: {result['module_count']}")


if __name__ == "__main__":
    main()

