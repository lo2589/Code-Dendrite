"""
锚点管理接口层
========================
generate_all_anchors: 从 5 个源 merge，写入 .codedendrite/anchors.json
load_anchors / get_anchor: 唯一读取接口
"""

import json
import os
import ast
import re as _re
from dataclasses import asdict
from pathlib import Path
from typing import Optional, List, Dict

from analyzer.shared.types import Anchor
from analyzer.shared.codedendrite_ignore import CodeDendriteIgnore
from analyzer.shared.formula_skip import should_skip as _should_skip_formula

_EMBED_STYLE_RE = _re.compile(r'<style[^>]*>(.*?)</style>', _re.DOTALL | _re.IGNORECASE)
_EMBED_SCRIPT_RE = _re.compile(r'<script[^>]*>(.*?)</script>', _re.DOTALL | _re.IGNORECASE)
_EMBED_DOM_ID_RE = _re.compile(r'\bid=["\']([A-Za-z][\w-]*)["\']')
_EMBED_CSS_SEL_RE = _re.compile(r'(?:^|[\s,>+~])([.#][A-Za-z][\w-]*)', _re.MULTILINE)
_EMBED_JS_FUNC_RE = _re.compile(r'function\s+([A-Za-z$_][\w$]*)\s*\(')
_EMBED_JS_QUERY_RE = _re.compile(r'(?:querySelectorAll?|getElementById)\s*\(\s*["\']([^"\']+)["\']')

# ── 调试日志（环境变量 CD_ANCHOR_LOG 开关；默认不打，不污染生产 run）──
import time as _time
_ANCHOR_DBG = bool(os.environ.get("CD_ANCHOR_LOG"))

from analyzer.anchors.subscript_string import ANCHOR_DEFAULTS, BUILTIN_NOISE, _subscript_string
from analyzer.anchors.call_site_collector import _call_name, _config_path, _factory_selector, _fstring_template, _CallSiteCollector, __all__, _alog
from analyzer.anchors.build_effective_methods_table import _anchor_to_storage, _build_unique_class_ids, _resolve_class_ref, _apply_inheritance_refs, _build_effective_methods_table, _build_unique_symbol_ids, _build_leaf_symbol_ids, _call_target, _code_anchor_symbol, _collect_import_aliases, _find_function_node, _extract_call_sites_from_tree, _extract_call_sites, _extract_function_io_from_tree, _extract_module_call_sites, _extract_registered_as, _registration_entries, _resolve_super_call
from analyzer.anchors.resolve import _JS_LANGUAGES, _resolve_import_attribute, _resolve_registered_call, _resolve_js_module_call, _resolve_js_factory_member, _resolve_call_id, _finalize_anchor_graph, _normalize_file_ref, _module_anchor_for_file, _normalize_registration_decorators
from analyzer.anchors.core_anchor import _merge_code_anchor, _merge_parsed_anchor, _generate_anchors_for_paths, _slow_warn, _write_anchors, check_all_anchors, create_anchor
from analyzer.anchors.core_load import load_anchors, filter_anchors_by_file
from analyzer.anchors.generate_all_anchors import generate_all_anchors
from analyzer.anchors.anchors_list import resolve_anchor_candidates, get_anchor, list_all_symbols, list_anchors, list_anchors_in_file, search_anchors, update_anchors_for_files

__all__ = ['ANCHOR_DEFAULTS', 'BUILTIN_NOISE', '_subscript_string', '_call_name', '_config_path', '_factory_selector', '_fstring_template', '_CallSiteCollector', '__all__', '_alog', '_anchor_to_storage', '_build_unique_class_ids', '_resolve_class_ref', '_apply_inheritance_refs', '_build_effective_methods_table', '_build_unique_symbol_ids', '_build_leaf_symbol_ids', '_call_target', '_code_anchor_symbol', '_collect_import_aliases', '_find_function_node', '_extract_call_sites_from_tree', '_extract_call_sites', '_extract_function_io_from_tree', '_extract_module_call_sites', '_extract_registered_as', '_registration_entries', '_resolve_super_call', '_JS_LANGUAGES', '_resolve_import_attribute', '_resolve_registered_call', '_resolve_js_module_call', '_resolve_js_factory_member', '_resolve_call_id', '_finalize_anchor_graph', '_normalize_file_ref', '_module_anchor_for_file', '_normalize_registration_decorators', '_merge_code_anchor', '_merge_parsed_anchor', '_generate_anchors_for_paths', '_slow_warn', '_write_anchors', 'check_all_anchors', 'create_anchor', 'load_anchors', 'filter_anchors_by_file', 'generate_all_anchors', 'resolve_anchor_candidates', 'get_anchor', 'list_all_symbols', 'list_anchors', 'list_anchors_in_file', 'search_anchors', 'update_anchors_for_files']
