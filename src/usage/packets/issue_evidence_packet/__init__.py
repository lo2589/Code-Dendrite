"""Build an evidence-preserving task packet from a complete issue description.

The packet deliberately separates extraction, matching, resolution, and action.
No candidate is promoted merely because it has the largest fuzzy score.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Optional

from usage.packets.task_context_packet import _anchor_attr, resolve_task_anchor


VERSION = "task_context_packet_v2"
MAX_SIGNALS = 64
MAX_CANDIDATES = 7
CODE_EXTENSIONS = (
    "py", "pyi", "js", "jsx", "ts", "tsx", "java", "go", "rs", "rb",
    "php", "c", "cc", "cpp", "h", "hpp", "cs", "kt", "kts", "scala",
)
GENERIC_IDENTIFIERS = {
    "args", "class", "code", "data", "error", "example", "false", "file",
    "from", "function", "issue", "kwargs", "line", "method", "module",
    "none", "object", "return", "self", "string", "test", "this", "true",
    "value", "when", "with",
}
KEYWORD_STOPWORDS = GENERIC_IDENTIFIERS | {
    "after", "before", "being", "does", "expected", "have", "into", "should",
    "that", "their", "there", "these", "they", "using", "which", "would",
}
SIGNAL_STRENGTH = {
    "anchor_id": 4,
    "traceback_frame": 4,
    "repo_path": 3,
    "api_name": 2,
    "exact_symbol": 2,
    "error_type": 0,
    "keyword": 0,
}

from usage.packets.issue_evidence_packet.validate_issue_evidence_packet import _anchors_at_line, _candidate_confidence, _normal_path, _match_files, _match_signal, _repo_files, _signal_key, extract_issue_signals, format_issue_packet_compact, validate_issue_evidence_packet
from usage.packets.issue_evidence_packet.issue_evidence import generate_issue_evidence_packet, save_issue_evidence_packet, main

__all__ = ['_anchors_at_line', '_candidate_confidence', '_normal_path', '_match_files', '_match_signal', '_repo_files', '_signal_key', 'extract_issue_signals', 'format_issue_packet_compact', 'validate_issue_evidence_packet', 'generate_issue_evidence_packet', 'save_issue_evidence_packet', 'main']
