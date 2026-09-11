from index.codeTree.anchor_engine_v2 import (
    create_anchor,
    list_anchors,
    compute_hash_v2,
    check_drift_v2 as check_drift,
    refresh_anchor,
    refresh_all_stale,
)

try:
    from synth.codeTree.agent_tools import TOOL_DEFINITIONS, handle_tool_call
except ImportError:
    TOOL_DEFINITIONS = []
    handle_tool_call = None

__all__ = [
    "create_anchor",
    "check_drift",
    "refresh_anchor",
    "refresh_all_stale",
    "list_anchors",
    "compute_hash_v2",
    "TOOL_DEFINITIONS",
    "handle_tool_call",
]
