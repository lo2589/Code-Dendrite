from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from tools.CodeDendrite.api.anchors import load_anchors


TYPE_LABELS = {
    "class": "class",
    "method": "method",
    "function": "function",
    "virtual_block": "raw-code",
}


def _anchor_label(anchor) -> str:
    symbol_type = getattr(anchor, "symbol_type", "") or ""
    if getattr(anchor, "is_virtual", False):
        virtual_kind = getattr(anchor, "virtual_kind", None)
        if virtual_kind:
            return "raw-code:{}".format(virtual_kind)
        return "raw-code"
    return TYPE_LABELS.get(symbol_type, symbol_type or "symbol")


def _anchor_name(anchor) -> str:
    symbol = getattr(anchor, "symbol", "") or getattr(anchor, "id", "")
    if getattr(anchor, "is_virtual", False):
        scope = getattr(anchor, "scope_label", None)
        if scope:
            return "{} ({})".format(symbol, scope)
    return symbol


def _write_dir(lines: list[str], name: str, node: dict, depth: int) -> None:
    indent = "  " * depth
    lines.append("{}- {}/".format(indent, name))
    for dirname in sorted(node["dirs"]):
        _write_dir(lines, dirname, node["dirs"][dirname], depth + 1)
    for filename in sorted(node["files"]):
        lines.append("{}  - {}".format(indent, filename))
        for anchor in sorted(
            node["files"][filename],
            key=lambda item: (getattr(item, "line_start", 0), getattr(item, "id", "")),
        ):
            label = _anchor_label(anchor)
            name = _anchor_name(anchor)
            lines.append(
                "{}    - [{}] {} `{}`".format(
                    indent,
                    label,
                    name,
                    getattr(anchor, "id", ""),
                )
            )


def generate_anchor_outline(root: str = ".", output: str | None = None) -> dict:
    """Generate a folder/file/symbol outline from existing anchors.json."""
    root_path = Path(root).resolve()
    output_path = Path(output) if output else root_path / ".codedendrite" / "anchor_outline.md"
    if not output_path.is_absolute():
        output_path = root_path / output_path

    anchors = load_anchors(str(root_path))
    tree = {"dirs": defaultdict(lambda: {"dirs": defaultdict(dict), "files": defaultdict(list)}), "files": defaultdict(list)}

    def make_node():
        return {"dirs": defaultdict(make_node), "files": defaultdict(list)}

    tree = make_node()
    for anchor in anchors.values():
        file_path = str(getattr(anchor, "file", "") or "").replace("\\", "/")
        if not file_path:
            continue
        parts = [part for part in file_path.split("/") if part]
        if not parts:
            continue
        node = tree
        for part in parts[:-1]:
            node = node["dirs"][part]
        node["files"][parts[-1]].append(anchor)

    lines = [
        "# CodeDendrite Anchor Outline",
        "",
        "Root: `{}`".format(root_path),
        "Anchors: {}".format(len(anchors)),
        "",
    ]
    for dirname in sorted(tree["dirs"]):
        _write_dir(lines, dirname, tree["dirs"][dirname], 0)
    for filename in sorted(tree["files"]):
        lines.append("- {}".format(filename))
        for anchor in sorted(
            tree["files"][filename],
            key=lambda item: (getattr(item, "line_start", 0), getattr(item, "id", "")),
        ):
            lines.append(
                "  - [{}] {} `{}`".format(
                    _anchor_label(anchor),
                    _anchor_name(anchor),
                    getattr(anchor, "id", ""),
                )
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
        f.write("\n")

    return {
        "output": str(output_path),
        "anchors": len(anchors),
        "lines": len(lines),
    }
