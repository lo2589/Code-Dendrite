"""
class_indexer.py - C++ 类索引构建器
=====================================
构建 C++ 项目的类索引，支持：
- 普通类
- 模板类
- 结构体
- 多继承
- 命名空间
- .h/.cpp 文件匹配

用法：
    from analyzer.inherit.language.cpp.class_indexer import build_class_index

    index = build_class_index("/path/to/project")
    for name, cls in index.classes.items():
        print(f"{name}: {cls.bases}")
"""

from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple

from analyzer.shared.legacy.cpp_inheritance.types import CppClassIndex, CppClassInfo, CppMethodInfo
from scanner.language.cpp.cpp_parser import parse_cpp_file, parse_cpp_directory, extract_implementation_methods

from analyzer.inherit.language.cpp.class_indexer.get_class_hierarchy import _is_in_namespace, _get_full_name, _merge_h_cpp_classes, _resolve_forward_declarations, build_class_index, _should_exclude, add_to_index, find_subclasses, find_template_instantiations, get_class_hierarchy, get_all_virtual_methods
from analyzer.inherit.language.cpp.class_indexer.resolve_multi_level_inheritance import resolve_multi_level_inheritance

__all__ = ['_is_in_namespace', '_get_full_name', '_merge_h_cpp_classes', '_resolve_forward_declarations', 'build_class_index', '_should_exclude', 'add_to_index', 'find_subclasses', 'find_template_instantiations', 'get_class_hierarchy', 'get_all_virtual_methods', 'resolve_multi_level_inheritance']
