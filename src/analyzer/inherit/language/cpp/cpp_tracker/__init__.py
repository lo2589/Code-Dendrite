"""
cpp_tracker.py - C++ 继承追踪封装类
====================================
C++ 继承追踪的统一接口，支持：
- 普通类和模板类
- 多继承
- 结构体
- 命名空间

用法：
    from analyzer.inherit.language.cpp.cpp_tracker import CppInheritanceTracker

    tracker = CppInheritanceTracker("/path/to/project")
    chain = tracker.resolve_inheritance("MyClass")
    mro = tracker.compute_mro("MyClass")
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from analyzer.shared.legacy.cpp_inheritance.types import CppClassIndex, CppClassInfo, CppLocation
from analyzer.inherit.language.cpp.class_indexer import (
    build_class_index, get_class_hierarchy,
    find_subclasses, get_all_virtual_methods,
    resolve_multi_level_inheritance
)
from analyzer.inherit.language.cpp.resolver import (
    resolve_inheritance, compute_mro, compute_full_mro,
    find_method_origin, get_override_chain, get_virtual_methods,
    is_subclass_of, get_all_bases, find_common_base
)

from analyzer.inherit.language.cpp.cpp_tracker.cpp_inheritance_tracker import CppInheritanceTracker
from analyzer.inherit.language.cpp.cpp_tracker.create_tracker import create_tracker

__all__ = ['CppInheritanceTracker', 'create_tracker']
