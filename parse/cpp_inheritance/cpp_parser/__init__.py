"""
cpp_parser.py - C++ AST 解析器
===============================
使用正则表达式进行 C++ 代码解析，支持：
- 类定义和继承
- 结构体定义
- 模板类
- 命名空间
- 虚函数和 override
- .h/.cpp 自动关联

支持 SLAM 等复杂 C++ 项目。

用法：
    from parse.cpp_inheritance.cpp_parser import parse_cpp_file

    info = parse_cpp_file("/path/to/file.cpp")
    for cls in info.classes:
        print(f"Class: {cls.name}, Bases: {cls.bases}")
"""

import re
from pathlib import Path
from typing import List, Optional, Dict, Set, Tuple

from base.cpp_inheritance.types import (
    CppClassInfo, CppMethodInfo, CppFileInfo,
    CppIncludeInfo, CppNamespaceInfo
)

from parse.cpp_inheritance.cpp_parser.core import CppParser
from parse.cpp_inheritance.cpp_parser.parse import extract_implementation_methods, parse_cpp_directory, parse_cpp_file

__all__ = ['CppParser', 'extract_implementation_methods', 'parse_cpp_directory', 'parse_cpp_file']
