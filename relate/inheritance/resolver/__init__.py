"""
resolver.py - 继承链解析器 (Hard L3-003, L3-004, L3-008, L3-009)
==================================================================
核心继承链追踪逻辑。

对应TS: inheritanceResolver.ts
"""

from pathlib import PurePosixPath
from typing import List, Optional, Union, Set, Dict, Any

from base.inheritance.types import (
    ClassIndex, ClassEntry, ExternalClassEntry,
    ImportInfo, Location, MethodInfo
)
from relate.inheritance.external_lib import resolve_external_class, get_builtin_class_info

from relate.inheritance.resolver.resolve_base_class import compute_full_mro, _c3_merge, _import_to_file_path, resolve_base_class
from relate.inheritance.resolver.find_method import resolve_inheritance, _resolve_recursive, compute_mro, find_method_origin, find_method_origin_with_class, get_overridden_methods, find_all_subclasses, find_method_in_chain
from relate.inheritance.resolver.resolve_bases import find_subclasses, resolve_all_bases, get_all_bases, resolve_base_class_safe

__all__ = ['compute_full_mro', '_c3_merge', '_import_to_file_path', 'resolve_base_class', 'resolve_inheritance', '_resolve_recursive', 'compute_mro', 'find_method_origin', 'find_method_origin_with_class', 'get_overridden_methods', 'find_all_subclasses', 'find_method_in_chain', 'find_subclasses', 'resolve_all_bases', 'get_all_bases', 'resolve_base_class_safe']
