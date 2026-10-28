"""CodeDendrite MCP Server

Exposes CodeDendrite's code analysis as MCP tools for Claude Code / Cursor.

Usage (add to .mcp.json):
  {
    "codedendrite": {
      "command": "python",
      "args": ["/path/to/CodeDendrite/mcp/server.py", "--root", "."]
    }
  }
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

# 各层包（analyzer / usage ...）的根是 src/，不设 PYTHONPATH 也要能导入
_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
for _p in (_HERE, _PARENT, os.path.join(_PARENT, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server


def _parse_root() -> str:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--root", default=".")
    args, _ = p.parse_known_args()
    return os.path.abspath(args.root)


ROOT = _parse_root()

# ── lazy cache ────────────────────────────────────────────────────────────────

_cache: dict = {}


def _anchors():
    if "anchors" not in _cache:
        from analyzer.anchors import load_anchors
        _cache["anchors"] = load_anchors(ROOT)
    return _cache["anchors"]


def _relations():
    if "relations" not in _cache:
        path = os.path.join(ROOT, ".codedendrite", "relations.json")
        with open(path, encoding="utf-8") as f:
            _cache["relations"] = json.load(f)
    return _cache["relations"]


def _module_tree():
    if "module_tree" not in _cache:
        path = os.path.join(ROOT, ".codedendrite", "module_tree.json")
        try:
            with open(path, encoding="utf-8") as f:
                _cache["module_tree"] = json.load(f)
        except FileNotFoundError:
            _cache["module_tree"] = {}
    return _cache["module_tree"]


def _project_summary() -> str:
    path = os.path.join(ROOT, ".codedendrite", "project_summary.md")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


# ── tool implementations ──────────────────────────────────────────────────────

def tool_context(query: str, level: str = "l2") -> str:
    """Task context packet for a symbol / keyword."""
    from usage.packets.task_context_packet import (
        resolve_task_anchor, build_level0, build_level1, build_level2,
    )
    anchors = _anchors()
    relations = _relations()
    module_tree = _module_tree()

    lv = level.lower()
    if lv == "l0":
        result = build_level0(ROOT, module_tree, anchors)
        return json.dumps(result, ensure_ascii=False, indent=2)
    matches = resolve_task_anchor(query, anchors)
    if not matches:
        return f"No anchor found for: {query}"
    if lv == "l1":
        result = build_level1(matches, module_tree, anchors, relations)
        return json.dumps(result, ensure_ascii=False, indent=2)

    # default l2
    area_info = build_level1(matches, module_tree, anchors, relations)
    result = build_level2(matches, area_info, anchors, relations, module_tree)
    return json.dumps(result, ensure_ascii=False, indent=2)


def tool_symbol(symbol: str) -> str:
    """Look up a symbol: file, line, callers, callees."""
    from usage.packets.task_context_packet import (
        resolve_task_anchor, build_anchor_packet,
    )
    anchors = _anchors()
    relations = _relations()
    matches = resolve_task_anchor(symbol, anchors)
    if not matches:
        return f"Symbol not found: {symbol}"
    packet = build_anchor_packet(matches, anchors, relations)
    return json.dumps(packet, ensure_ascii=False, indent=2)


def tool_search(keyword: str, limit: int = 20) -> str:
    """Search anchors by keyword (symbol name, file path, or free text)."""
    from usage.packets.task_context_packet import resolve_task_anchor
    anchors = _anchors()
    matches = resolve_task_anchor(keyword, anchors)
    rows = []
    for aid, anchor, match_type in matches[:limit]:
        rows.append({
            "id": aid,
            "file": getattr(anchor, "file", anchor.get("file", "") if isinstance(anchor, dict) else ""),
            "line": getattr(anchor, "line_start", anchor.get("line_start", 0) if isinstance(anchor, dict) else 0),
            "match": match_type,
        })
    if not rows:
        # fallback: substring search on all anchor ids
        kw = keyword.lower()
        for aid, anchor in anchors.items():
            if kw in aid.lower():
                rows.append({"id": aid, "match": "substring"})
            if len(rows) >= limit:
                break
    return json.dumps(rows, ensure_ascii=False, indent=2)


def tool_impact(symbol: str, limit: int = 15) -> str:
    """What is affected if this symbol changes? Returns impact + call chain."""
    relations = _relations()
    anchors = _anchors()
    edges = relations.get("edges", [])

    # find anchor id for symbol
    target_id = None
    for aid in anchors:
        if aid == symbol or aid.endswith("::" + symbol):
            target_id = aid
            break
    if not target_id:
        return f"Symbol not found: {symbol}"

    # collect downstream (impact) edges
    impacted = []
    for edge in edges:
        if edge.get("from_id") == target_id:
            impacted.append({
                "symbol": edge["to_id"],
                "type": edge.get("edge_type", "?"),
            })
        if len(impacted) >= limit:
            break

    # collect upstream (who calls this)
    callers = []
    for edge in edges:
        if edge.get("to_id") == target_id:
            callers.append({
                "symbol": edge["from_id"],
                "type": edge.get("edge_type", "?"),
            })
        if len(callers) >= limit:
            break

    return json.dumps({
        "target": target_id,
        "callers": callers,
        "impacts": impacted,
    }, ensure_ascii=False, indent=2)


def tool_modules(query: str = "") -> str:
    """List semantic modules, optionally filtered by query."""
    summary = _project_summary()
    if not query:
        return summary or "No project summary available. Run: python -m api.cli <root> --update"

    # filter lines containing query
    lines = summary.splitlines()
    result = []
    capture = False
    for line in lines:
        if query.lower() in line.lower():
            capture = True
        if capture:
            result.append(line)
            if len(result) > 20:
                break
    return "\n".join(result) if result else f"No module matching: {query}"


# ── MCP server ────────────────────────────────────────────────────────────────

app = Server("codedendrite")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="cd_context",
            description=(
                "Get a pre-packaged task context (L0/L1/L2) for a symbol or keyword. "
                "Returns callers, callees, module area, and ranked candidates — ready to paste into a prompt. "
                "Use this before editing or debugging any symbol."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Symbol name, file::symbol, or free-text keyword"},
                    "level": {"type": "string", "enum": ["l0", "l1", "l2"], "default": "l2",
                              "description": "l0=project brief, l1=area map, l2=task slice (default)"},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="cd_symbol",
            description=(
                "Look up a symbol: exact file path, line number, callers (who calls it) and callees (what it calls). "
                "Use this to navigate to a definition or understand dependencies."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Symbol name or file::symbol id"},
                },
                "required": ["symbol"],
            },
        ),
        types.Tool(
            name="cd_search",
            description="Search all anchors by keyword (symbol name, file path, or substring). Returns matching anchor ids and locations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["keyword"],
            },
        ),
        types.Tool(
            name="cd_impact",
            description=(
                "Show what is affected if a symbol changes: who calls it (callers) and what it calls downstream (impacts). "
                "Use before refactoring to understand blast radius."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Symbol name or file::symbol id"},
                    "limit": {"type": "integer", "default": 15},
                },
                "required": ["symbol"],
            },
        ),
        types.Tool(
            name="cd_modules",
            description="List semantic modules of the codebase with entry points and descriptions. Optionally filter by query.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "default": "", "description": "Filter modules by name or keyword"},
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        if name == "cd_context":
            result = tool_context(arguments["query"], arguments.get("level", "l2"))
        elif name == "cd_symbol":
            result = tool_symbol(arguments["symbol"])
        elif name == "cd_search":
            result = tool_search(arguments["keyword"], arguments.get("limit", 20))
        elif name == "cd_impact":
            result = tool_impact(arguments["symbol"], arguments.get("limit", 15))
        elif name == "cd_modules":
            result = tool_modules(arguments.get("query", ""))
        else:
            result = f"Unknown tool: {name}"
    except Exception as e:
        result = f"Error: {type(e).__name__}: {e}"

    return [types.TextContent(type="text", text=result)]


async def _main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(_main())
