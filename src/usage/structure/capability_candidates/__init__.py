"""
能力候选提取器
========================
从静态证据（锚点 + 关系 + 路径策略）中提取能力候选，
供 module_tree_v2.py 合并成最终模块。

能力候选 = 高层锚点 + 局部邻域证据 + 引用证据 + 打分

用法:
    from usage.structure.capability_candidates import build_capability_candidates

    result = build_capability_candidates("/path/to/project")
    # -> { "version": ..., "candidates": [...], "summary": {...} }
"""

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Optional

from usage.path_policy import (
    PathPolicy,
    classify_path_role,
    load_path_policy,
    normalize_project_path,
)


# ── 锚点适配（兼容 Anchor 对象和 dict）──────────────────────────

from usage.structure.capability_candidates.count_call_fanout import score_candidate, _infer_area, _is_low_distinctiveness_name, _get_file_from_id, _count_distinct_caller_files, _count_call_fanout, _is_private_symbol, attach_reference_evidence, _count_call_fanin
from usage.structure.capability_candidates.build_capability_candidates import _anchor_attr, _build_edge_indexes, _build_file_anchor_index, detect_high_level_anchor, _infer_candidate_name, build_candidate_seed, attach_relation_evidence, _discover_component_root_candidates, build_capability_candidates, save_capability_candidates

__all__ = ['score_candidate', '_infer_area', '_is_low_distinctiveness_name', '_get_file_from_id', '_count_distinct_caller_files', '_count_call_fanout', '_is_private_symbol', 'attach_reference_evidence', '_count_call_fanin', '_anchor_attr', '_build_edge_indexes', '_build_file_anchor_index', 'detect_high_level_anchor', '_infer_candidate_name', 'build_candidate_seed', 'attach_relation_evidence', '_discover_component_root_candidates', 'build_capability_candidates', 'save_capability_candidates']
