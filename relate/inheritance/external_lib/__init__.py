"""
external_lib.py - 外部库解析 (Medium L3-005, Hard L3-006, Easy L3-007)
========================================================================
解析外部库和内置类。

对应TS: externalLibResolver.ts
"""

from pathlib import Path
from typing import List, Optional, Dict
import sys

from base.inheritance.types import ExternalClassEntry, MethodInfo
from parse.inheritance.ast_parser import parse_python_file


# 缓存
_site_packages_cache: List[str] = []
_external_class_cache: Dict[str, ExternalClassEntry] = {}

from relate.inheritance.external_lib.get_builtin_class_info import clear_cache, get_builtin_class_info, get_common_frameworks_classes, get_site_packages_paths, resolve_module_path
from relate.inheritance.external_lib.resolve_external_class import resolve_external_class

__all__ = ['clear_cache', 'get_builtin_class_info', 'get_common_frameworks_classes', 'get_site_packages_paths', 'resolve_module_path', 'resolve_external_class']
