"""Task Context Packet — 给小模型/执行 agent 生成当前任务的窄上下文包。

设计文档: todo/codedentrite/CD_四类结构图认知整理.md §4

四级上下文:
  Level 0: Project Brief (30-80 tokens)  — 项目一句话 + 顶层区域
  Level 1: Area Map (100-300 tokens)     — 当前任务所在区域
  Level 2: Task Slice (300-800 tokens)   — 0-3 个可信候选 + why + next_command
  Level 3: Source Snippet (按需)         — 默认不给

验收标准:
  1. Level 0 不超过 3 句
  2. Level 1 只描述当前区域
  3. Level 2 只给有证据支撑的候选，不为满足数量下限而补齐
  4. 每个候选都有 why 和 next_command
  5. 不默认给源码片段
  6. 小模型能只根据 packet 选择下一步
"""

import json
import os
import ast
import re
from pathlib import Path
from collections import defaultdict
from typing import Optional, List, Tuple, Any, Callable


# ── 常量 ─────────────────────────────────────────────────────────

DEFAULT_BUDGET = 1200   # 总 token 预算
L0_TOKEN_LIMIT = 80
L1_TOKEN_LIMIT = 300
L2_TOKEN_LIMIT = 800
MAX_CANDIDATES = 7
MIN_CANDIDATES = 0
RECOMMENDATION_LIMIT = 3
NOISE_SYMBOLS = {
    "print", "len", "str", "int", "float", "bool", "list", "dict", "set",
    "Path", "open", "json.dumps", "json.loads", "time.sleep",
}
GENERIC_TASK_QUERIES = {
    "all", "binary", "code", "error", "extract", "file", "interactive",
    "line", "message", "module", "previous", "python", "range", "return",
    "self", "text", "the", "this", "value",
}
FILE_MATCH_TYPES = {"file_path", "file_suffix", "file_stem", "file_segment"}


# ── 工具函数 ─────────────────────────────────────────────────────

from synth.api.task_context_packet.plugin import _plugin_error, _plugin_framework, _plugin_navigation, _plugin_project, _plugin_source, _plugin_anchor, _plugin_control, LARGE_PROMPT_PLUGINS, SMALL_PROMPT_PLUGINS, _is_test_file, _find_anchor_module, _estimate_tokens, _estimate_obj_tokens, _short_condition, _call_name, _control_path_for_call, _symbol_tail, _is_noise_symbol, build_error_packet, assemble_task_prompt, _relation_resolution_counts
from synth.api.task_context_packet.anchor import _anchor_attr, _anchor_id, _match_sort_key, _bounded_matches, _read_anchor_source, resolve_task_anchor, assess_task_matches, _build_edge_indexes, build_level0, _find_anchor_area, build_level1, _score_related_symbol, build_level2, match_anchor_from_error, build_anchor_packet, build_control_packet, build_source_slices, generate_task_context
from synth.api.task_context_packet.format_compact import format_compact, format_compact_tokens, save_task_context

__all__ = ['_plugin_error', '_plugin_framework', '_plugin_navigation', '_plugin_project', '_plugin_source', '_plugin_anchor', '_plugin_control', 'LARGE_PROMPT_PLUGINS', 'SMALL_PROMPT_PLUGINS', '_is_test_file', '_find_anchor_module', '_estimate_tokens', '_estimate_obj_tokens', '_short_condition', '_call_name', '_control_path_for_call', '_symbol_tail', '_is_noise_symbol', 'build_error_packet', 'assemble_task_prompt', '_relation_resolution_counts', '_anchor_attr', '_anchor_id', '_match_sort_key', '_bounded_matches', '_read_anchor_source', 'resolve_task_anchor', 'assess_task_matches', '_build_edge_indexes', 'build_level0', '_find_anchor_area', 'build_level1', '_score_related_symbol', 'build_level2', 'match_anchor_from_error', 'build_anchor_packet', 'build_control_packet', 'build_source_slices', 'generate_task_context', 'format_compact', 'format_compact_tokens', 'save_task_context']
