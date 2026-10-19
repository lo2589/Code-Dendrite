"""
cpp_inheritance - C++ 继承追踪系统
===================================
支持 C++ 类、结构体、模板类的继承链追踪。

主要功能：
- 解析 C++ 文件和目录
- 构建类索引
- 追踪继承链
- 计算 MRO
- 支持多继承和模板类

用法：
    from analyzer.inherit.language.cpp import CppInheritanceTracker

    tracker = CppInheritanceTracker("/path/to/project")
    chain = tracker.resolve_inheritance("MyClass")
"""

from analyzer.shared.legacy.cpp_inheritance.types import (
    CppClassInfo,
    CppMethodInfo,
    CppFileInfo,
    CppClassIndex,
    CppLocation,
    CppIncludeInfo,
    CppNamespaceInfo,
    CppInheritanceEntry,
    CppExternalClassEntry,
    CppSuperCallInfo,
    CppOverrideInfo,
)

from scanner.language.cpp.cpp_parser import (
    parse_cpp_file,
    parse_cpp_directory,
    CppParser,
)

from analyzer.inherit.language.cpp.class_indexer import (
    build_class_index,
    add_to_index,
    get_class_hierarchy,
    find_subclasses,
    find_template_instantiations,
    get_all_virtual_methods,
)

from analyzer.inherit.language.cpp.resolver import (
    resolve_inheritance,
    compute_mro,
    compute_full_mro,
    find_method_origin,
    get_override_chain,
    get_virtual_methods,
    is_subclass_of,
    get_all_bases,
    find_common_base,
)

from analyzer.inherit.language.cpp.cpp_tracker import (
    CppInheritanceTracker,
    create_tracker,
)

__all__ = [
    # 类型
    'CppClassInfo',
    'CppMethodInfo',
    'CppFileInfo',
    'CppClassIndex',
    'CppLocation',
    'CppIncludeInfo',
    'CppNamespaceInfo',
    'CppInheritanceEntry',
    'CppExternalClassEntry',
    'CppSuperCallInfo',
    'CppOverrideInfo',

    # 解析器
    'parse_cpp_file',
    'parse_cpp_directory',
    'CppParser',

    # 索引
    'build_class_index',
    'add_to_index',
    'get_class_hierarchy',
    'find_subclasses',
    'find_template_instantiations',
    'get_all_virtual_methods',

    # 解析器
    'resolve_inheritance',
    'compute_mro',
    'compute_full_mro',
    'find_method_origin',
    'get_override_chain',
    'get_virtual_methods',
    'is_subclass_of',
    'get_all_bases',
    'find_common_base',

    # 追踪器
    'CppInheritanceTracker',
    'create_tracker',
]
