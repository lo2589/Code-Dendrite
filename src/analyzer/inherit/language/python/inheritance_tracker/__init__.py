"""
inheritance_tracker.py - Python 继承追踪封装类
================================================
从 TypeScript 迁移并增强的 Python 继承链追踪工具。

功能：
- 封装 resolver.py 中的函数为类接口
- 支持跨文件和外部库的继承链追踪
- 支持多继承和 C3 线性化
- 支持方法覆盖和 super() 调用分析

用法：
    from analyzer.inherit.language.python.inheritance_tracker import InheritanceTracker

    tracker = InheritanceTracker("/path/to/project")
    chain = tracker.resolve_inheritance("MyClass")
    mro = tracker.compute_mro("MyClass")
    origin = tracker.find_method_origin("MyClass", "my_method")
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Set

from analyzer.shared.legacy.inheritance.types import (
    ClassIndex, ClassEntry, ExternalClassEntry, Location,
    MethodInfo, ClassInfo
)
from analyzer.inherit.class_indexer import build_class_index
from analyzer.inherit.language.python.resolver import (
    resolve_inheritance, resolve_base_class, compute_mro as _compute_mro,
    find_method_origin as _find_method_origin,
    find_method_origin_with_class
)
from analyzer.inherit.language.python.external_lib import get_builtin_class_info, resolve_external_class

from analyzer.inherit.language.python.inheritance_tracker.core import InheritanceTracker
from analyzer.inherit.language.python.inheritance_tracker.create_tracker import create_tracker

__all__ = ['InheritanceTracker', 'create_tracker']
