"""
Agent Tool Registry for CodeAnchor
------------------------------------
Drop-in tool definitions compatible with OpenAI / Anthropic function-calling format.
Import TOOL_DEFINITIONS and the handler to wire into your Copilot agent.

Usage in your agent:
    from usage.analyze.agent_tools import TOOL_DEFINITIONS, handle_tool_call

    # Register tools with your agent framework:
    agent.register_tools(TOOL_DEFINITIONS)

    # In your tool execution handler:
    result = handle_tool_call(tool_name, tool_args)
"""

from analyzer.identity.engine_v1 import (
    create_anchor,
    check_drift,
    refresh_anchor,
    list_anchors,
)

# ─────────────────────────────────────────────
# JSON Schema tool definitions
# Compatible with Anthropic tool_use and OpenAI function_calling
# ─────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "create_anchor",
        "description": (
            "Bind a documentation description to a specific code fragment. "
            "Computes a hash of the target code and stores the binding. "
            "Returns an @anchor tag to paste into the doc. "
            "Use when writing or updating documentation to lock it to the current code state."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "anchor_id": {
                    "type": "string",
                    "description": "Dot-path logical name, e.g. 'auth.login.validate' or 'db.models.User'",
                },
                "file": {
                    "type": "string",
                    "description": "Path to source file relative to project root, e.g. 'src/auth/login.py'",
                },
                "symbol": {
                    "type": "string",
                    "description": (
                        "Optional. Python symbol to hash. "
                        "Can be 'function_name', 'ClassName', or 'ClassName.method_name'. "
                        "If omitted, hashes the entire file."
                    ),
                },
                "line_start": {
                    "type": "integer",
                    "description": "Optional. Start line (1-indexed) for line-range mode.",
                },
                "line_end": {
                    "type": "integer",
                    "description": "Optional. End line for line-range mode.",
                },
                "description": {
                    "type": "string",
                    "description": "Human-readable label shown in drift reports, e.g. 'Handles JWT validation'",
                },
                "root": {
                    "type": "string",
                    "description": "Project root directory. Defaults to current directory '.'",
                },
            },
            "required": ["anchor_id", "file"],
        },
    },
    {
        "name": "check_drift",
        "description": (
            "Check which documentation anchors have drifted — i.e. the code has changed "
            "since the doc was last anchored. "
            "CALL THIS AT THE START OF EVERY SESSION before reading or modifying code. "
            "Stale anchors mean the documentation may be lying. "
            "Returns lists of stale, missing, and ok anchors with a plain-text summary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "anchor_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional. Specific anchor IDs to check. If omitted, checks all registered anchors.",
                },
                "doc_text": {
                    "type": "string",
                    "description": (
                        "Optional. Raw text of a document containing @anchor{...} tags. "
                        "These will be extracted and checked alongside anchor_ids."
                    ),
                },
                "root": {
                    "type": "string",
                    "description": "Project root directory. Defaults to '.'",
                },
            },
            "required": [],
        },
    },
    {
        "name": "refresh_anchor",
        "description": (
            "After modifying code, recompute the hash for an anchor and update the stored binding. "
            "Returns the new @anchor tag to replace in the documentation. "
            "Call this AFTER completing code changes to keep anchors in sync."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "anchor_id": {
                    "type": "string",
                    "description": "The anchor ID to refresh.",
                },
                "root": {
                    "type": "string",
                    "description": "Project root directory. Defaults to '.'",
                },
            },
            "required": ["anchor_id"],
        },
    },
    {
        "name": "list_anchors",
        "description": (
            "List all registered anchors with their current drift status. "
            "Useful for giving the agent a full picture of what documentation is tracked "
            "and which areas of the codebase are covered."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "root": {
                    "type": "string",
                    "description": "Project root directory. Defaults to '.'",
                },
            },
            "required": [],
        },
    },
]


# ─────────────────────────────────────────────
# Unified handler
# ─────────────────────────────────────────────

_TOOL_MAP = {
    "create_anchor": create_anchor,
    "check_drift": check_drift,
    "refresh_anchor": refresh_anchor,
    "list_anchors": list_anchors,
}


def handle_tool_call(tool_name: str, tool_args: dict) -> dict:
    """
    Central dispatcher. Call from your agent's tool execution loop.

    Example:
        for block in response.content:
            if block.type == "tool_use":
                result = handle_tool_call(block.name, block.input)
                # feed result back as tool_result message
    """
    fn = _TOOL_MAP.get(tool_name)
    if fn is None:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return fn(**tool_args)
    except Exception as e:
        return {"error": str(e), "tool": tool_name, "args": tool_args}
