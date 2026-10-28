"""
Deep Drift Analyzer
--------------------
专门处理大幅度增删改之后的"找回"问题。

普通 check_drift() 对每个锚点独立检查 → 适合日常小改动
deep_drift_report() 做全局分析 → 适合大重构之后

核心能力：
1. 找出所有 stale/missing 锚点，并附上具体 diff
2. 用智能 AI（一次调用）生成跨文件的变更叙述
3. 对 missing 锚点尝试"模糊匹配"——在现有代码里找最像原来的东西
4. 输出 Markdown 报告，直接可以粘贴进 CLAUDE.md
"""

import ast
import os
import difflib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from analyzer.identity.engine import (
    Anchor, check_drift_v2 as check_drift, compute_hash_v2 as compute_hash,
    _load_db, _save_db,
    _extract_symbol_source_v2 as _extract_symbol_source,
)


# ─────────────────────────────────────────────
# Git helpers
# ─────────────────────────────────────────────

from analyzer.repair.deep_drift.list_all_symbols import AnchorDriftDetail, _DEFAULT_EXCLUDE_DIRS, _NARRATIVE_PROMPT, _build_action_items, git_log_files, _generate_narrative, _list_all_symbols, _render_markdown, git_show_deleted, git_diff_file, fuzzy_find_symbol
from analyzer.repair.deep_drift.deep_drift_report import deep_drift_report

__all__ = ['AnchorDriftDetail', '_DEFAULT_EXCLUDE_DIRS', '_NARRATIVE_PROMPT', '_build_action_items', 'git_log_files', '_generate_narrative', '_list_all_symbols', '_render_markdown', 'git_show_deleted', 'git_diff_file', 'fuzzy_find_symbol', 'deep_drift_report']
