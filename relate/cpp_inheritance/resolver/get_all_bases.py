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

from relate.cpp_inheritance.resolver.normalize_class_name import _normalize_class_name

def get_all_bases(
    index: CppClassIndex,
    class_name: str
) -> List[str]:
    """
    获取类的所有基类（多继承）

    参数：
        index: 类索引
        class_name: 类名

    返回：
        所有基类列表
    """
    all_bases = []
    visited = set()

    def collect(name: str):
        if name in visited:
            return
        visited.add(name)

        cls = index.get(name)
        if cls:
            for base in cls.bases:
                base_name = _normalize_class_name(base)
                all_bases.append(base_name)
                collect(base_name)

    collect(class_name)
    return all_bases
