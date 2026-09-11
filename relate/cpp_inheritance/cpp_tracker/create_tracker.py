"""
cpp_tracker.py - C++ 继承追踪封装类
====================================
C++ 继承追踪的统一接口，支持：
- 普通类和模板类
- 多继承
- 结构体
- 命名空间

用法：
    from relate.cpp_inheritance.cpp_tracker import CppInheritanceTracker

    tracker = CppInheritanceTracker("/path/to/project")
    chain = tracker.resolve_inheritance("MyClass")
    mro = tracker.compute_mro("MyClass")
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from base.cpp_inheritance.types import CppClassIndex, CppClassInfo, CppLocation
from index.cpp_inheritance.class_indexer import (
    build_class_index, get_class_hierarchy,
    find_subclasses, get_all_virtual_methods,
    resolve_multi_level_inheritance
)
from relate.cpp_inheritance.resolver import (
    resolve_inheritance, compute_mro, compute_full_mro,
    find_method_origin, get_override_chain, get_virtual_methods,
    is_subclass_of, get_all_bases, find_common_base
)

from relate.cpp_inheritance.cpp_tracker.cpp_inheritance_tracker import CppInheritanceTracker

def create_tracker(root: str) -> CppInheritanceTracker:
    """
    创建追踪器的便捷函数

    参数：
        root: 项目根目录

    返回：
        CppInheritanceTracker 实例
    """
    return CppInheritanceTracker(root)
