"""
string_dispatch.py — 字符串路由边提取
====================================
扫描 Python AST，提取 if/elif 字符串比较条件下的调用关系。

支持的语法：
- if method == "xxx": self._handle_xxx(...)
- elif action == "yyy": await self._handle_yyy(...)
- return self.handler(...)

不支持的语法（本次不做）：
- match/case
- dict dispatch
- in / not in
- and / or 组合条件
"""

import ast
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from scanner.calls.string_dispatch.extract_called_symbols import __all__, _attach_parents, _build_dispatch_edge, _build_function_id, _extract_call_target, _extract_called_symbols, _extract_compare_parts, _find_enclosing_class, _is_elif_node, _is_string_compare, _walk_if_chain
from scanner.calls.string_dispatch.dispatches_extract import extract_dispatches_from_function, extract_dispatches_from_file, find_string_dispatches
from scanner.calls.string_dispatch.dispatches_per_language import (
    extract_dispatches_for_path,
    extract_dispatches_from_go,
    extract_dispatches_from_java,
    extract_dispatches_from_js,
    extract_dispatches_from_kotlin,
)

__all__ = ['__all__', '_attach_parents', '_build_dispatch_edge', '_build_function_id', '_extract_call_target', '_extract_called_symbols', '_extract_compare_parts', '_find_enclosing_class', '_is_elif_node', '_is_string_compare', '_walk_if_chain', 'extract_dispatches_from_function', 'extract_dispatches_from_file', 'find_string_dispatches', 'extract_dispatches_for_path', 'extract_dispatches_from_go', 'extract_dispatches_from_java', 'extract_dispatches_from_js', 'extract_dispatches_from_kotlin']
