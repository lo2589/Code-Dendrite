from __future__ import annotations

"""
CodeDendrite command-line entry point.

Examples:
    python api/cli.py D:\repo
    python api/cli.py D:\repo --update
    python api/cli.py D:\repo --debug-loop --file backend/main.py --error "..."
"""
import argparse
import ast
import os
import sys
from collections import Counter

from usage.cli.module import _cmd_capability_candidates, _cmd_module_tree_v2, _cmd_module_tree_v2_check, _cmd_module_tree_v2_html, _cmd_path_policy_check, _cmd_task_context, _cmd_task_context_compact, _print_debug_loop, debug_loop, _print_relations, module_graph, _parse_conditions, anchor_outline, _print_module, module_query
from usage.cli.ensure_path import _ensure_path, rebuild, update, external_deps, main

__all__ = ['_cmd_capability_candidates', '_cmd_module_tree_v2', '_cmd_module_tree_v2_check', '_cmd_module_tree_v2_html', '_cmd_path_policy_check', '_cmd_task_context', '_cmd_task_context_compact', '_print_debug_loop', 'debug_loop', '_print_relations', 'module_graph', '_parse_conditions', 'anchor_outline', '_print_module', 'module_query', '_ensure_path', 'rebuild', 'update', 'external_deps', 'main']
