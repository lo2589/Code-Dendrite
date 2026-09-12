"""
模块树 V2 生成器
========================
从 capability_candidates 合并生成项目级功能块导览图。

核心流程:
  candidates → module kernels → merge → 四格填充 → status/confidence → edges → completeness

用法:
    from usage.structure.module_tree_v2 import generate_module_tree_v2

    tree = generate_module_tree_v2("/path/to/project")
    # -> { "version": "module_tree_v2", "modules": [...], ... }
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

from usage.path_policy import (
    PathPolicy,
    classify_path_role,
    load_path_policy,
)
from usage.structure.capability_candidates import (
    build_capability_candidates,
    _build_edge_indexes,
    _anchor_attr,
)


# ── 模块核生成 ──────────────────────────────────────────────────

from usage.structure.module_tree_v2.module_assign import _attach_supplements_to_modules, _clean_module, _compute_merge_score, _dedup, _create_area_module, _create_module_from_seed, _detect_fake_module, _merge_modules, assign_module_confidence, assign_module_name, assign_module_status
from usage.structure.module_tree_v2.module_completeness import build_completeness_report, build_module_edges, build_module_kernels, fill_module_slots, merge_module_candidates
from usage.structure.module_tree_v2.module_tree import generate_module_tree_v2, save_module_tree_v2

__all__ = ['_attach_supplements_to_modules', '_clean_module', '_compute_merge_score', '_dedup', '_create_area_module', '_create_module_from_seed', '_detect_fake_module', '_merge_modules', 'assign_module_confidence', 'assign_module_name', 'assign_module_status', 'build_completeness_report', 'build_module_edges', 'build_module_kernels', 'fill_module_slots', 'merge_module_candidates', 'generate_module_tree_v2', 'save_module_tree_v2']
