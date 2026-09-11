"""
resolver.py - C++ 继承链解析器
=================================
解析 C++ 类的继承链，支持：
- 多继承
- 模板类
- 命名空间
- 外部库

用法：
    from relate.cpp_inheritance.resolver import resolve_inheritance, compute_mro

    chain = resolve_inheritance(index, "MyClass")
    mro = compute_mro(index, "MyClass")
"""

from typing import List, Optional, Set, Dict, Any
import re

from base.cpp_inheritance.types import CppClassIndex, CppClassInfo, CppInheritanceEntry, CppLocation

from relate.cpp_inheritance.resolver.normalize_class_name import _normalize_class_name, compute_full_mro, _c3_merge, resolve_inheritance, _resolve_recursive, compute_mro, find_method_origin, get_override_chain, get_virtual_methods, is_subclass_of, find_common_base
from relate.cpp_inheritance.resolver.get_all_bases import get_all_bases

__all__ = ['_normalize_class_name', 'compute_full_mro', '_c3_merge', 'resolve_inheritance', '_resolve_recursive', 'compute_mro', 'find_method_origin', 'get_override_chain', 'get_virtual_methods', 'is_subclass_of', 'find_common_base', 'get_all_bases']
