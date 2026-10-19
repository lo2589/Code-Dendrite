"""
L3_Inheritance - 继承链追踪系统
================================
从TypeScript迁移的Python继承链分析工具。
支持 Python 和 C++ 继承追踪。

主要类:
- InheritanceTracker: Python 继承追踪器
- CppInheritanceTracker: C++ 继承追踪器（cpp_inheritance 模块）

主要函数:
- build_class_index(): 构建类索引 (Medium L3-001)
- parse_python_file(): 解析Python文件 (Easy L3-002)
- resolve_inheritance(): 解析继承链 (Hard L3-003)
- resolve_base_class(): 解析基类 (Hard L3-004)
- get_site_packages_paths(): 获取site-packages路径 (Medium L3-005)
- resolve_external_class(): 解析外部库类 (Hard L3-006)
- get_builtin_class_info(): 获取内置类信息 (Easy L3-007)
- compute_mro(): 计算MRO (Hard L3-008)
- find_method_origin(): 查找方法定义位置 (Hard L3-009)

新增功能:
- InheritanceTracker: 封装类，提供更友好的接口
- analyze_super_calls(): 分析 super() 调用
- build_override_chain(): 构建方法覆盖链
"""

from analyzer.shared.legacy.inheritance.types import (
    MethodInfo, ClassInfo, ImportInfo, PythonFileInfo,
    ClassEntry, ExternalClassEntry, Location, ClassIndex
)
from scanner.language.python.ast_parser import parse_python_file
from analyzer.inherit.class_indexer import build_class_index
from analyzer.inherit.language.python.resolver import (
    resolve_inheritance, resolve_base_class, compute_mro, find_method_origin,
    resolve_all_bases, find_method_in_chain, resolve_base_class_safe, get_all_bases, find_subclasses
)
from analyzer.inherit.language.python.external_lib import (
    get_site_packages_paths, resolve_external_class,
    get_builtin_class_info, resolve_module_path
)
from analyzer.inherit.language.python.inheritance_tracker import InheritanceTracker, create_tracker
from analyzer.inherit.language.python.super_analyzer import analyze_super_calls, find_super_in_method, validate_super_calls
from analyzer.inherit.language.python.override_analyzer import build_override_chain, find_overridden_method

__all__ = [
    # 类型
    'MethodInfo',
    'ClassInfo',
    'ImportInfo',
    'PythonFileInfo',
    'ClassEntry',
    'ExternalClassEntry',
    'Location',
    'ClassIndex',

    # 核心函数
    'parse_python_file',
    'build_class_index',
    'resolve_inheritance',
    'resolve_base_class',
    'get_site_packages_paths',
    'resolve_external_class',
    'get_builtin_class_info',
    'compute_mro',
    'find_method_origin',

    # 增强函数
    'resolve_all_bases',
    'get_all_bases',
    'find_subclasses',
    'find_method_in_chain',
    'resolve_base_class_safe',
    'resolve_module_path',

    # 追踪器
    'InheritanceTracker',
    'create_tracker',

    # super() 分析
    'analyze_super_calls',
    'find_super_in_method',
    'validate_super_calls',

    # override 分析
    'build_override_chain',
    'find_overridden_method',
]
