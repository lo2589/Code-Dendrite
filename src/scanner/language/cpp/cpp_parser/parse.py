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
    from scanner.language.cpp.cpp_parser import parse_cpp_file

    info = parse_cpp_file("/path/to/file.cpp")
    for cls in info.classes:
        print(f"Class: {cls.name}, Bases: {cls.bases}")
"""

import re
from pathlib import Path
from typing import List, Optional, Dict, Set, Tuple

from scanner.shared.cpp_inheritance_types import (
    CppClassInfo, CppMethodInfo, CppFileInfo,
    CppIncludeInfo, CppNamespaceInfo
)

from scanner.language.cpp.cpp_parser.core import CppParser

def extract_implementation_methods(cpp_file_path: str) -> Dict[str, List[CppMethodInfo]]:
    """
    从 .cpp 文件中提取方法实现

    返回：
        {
            "ClassName::method_name": [CppMethodInfo, ...],
            ...
        }
    """
    path = Path(cpp_file_path)
    if not path.exists():
        return {}

    content = path.read_text(encoding='utf-8', errors='ignore')

    method_impl_pattern = re.compile(
        r'([A-Za-z_][A-Za-z0-9_]*)\s*::\s*([A-Za-z_~][A-Za-z0-9_]*)'
        r'\s*\([^)]*\)'
        r'(?:\s*:\s*[^^{]*)?'
        r'(?:\s*const)?'
        r'\s*\{',
        re.MULTILINE | re.DOTALL
    )

    result = {}

    for match in method_impl_pattern.finditer(content):
        full_match = match.group(0)
        line = content[:match.start()].count('\n') + 1

        class_name = match.group(1)
        method_name = match.group(2)

        params_match = re.search(r'\(([^)]*)\)', match.group(0))
        params_str = params_match.group(1) if params_match else ''
        param_list = [p.strip() for p in params_str.split(',') if p.strip()]

        method_info = CppMethodInfo(
            name=method_name,
            start_line=line,
            end_line=0,
            return_type='',
            parameters=param_list,
            is_virtual=False,
            is_override=False,
            is_pure_virtual=False,
            is_const='const' in full_match,
            access='public',
            is_implementation=True,
            impl_file=cpp_file_path
        )

        key = f"{class_name}::{method_name}"
        if key not in result:
            result[key] = []
        result[key].append(method_info)

    return result

def parse_cpp_directory(directory: str, extensions: List[str] = None) -> List[CppFileInfo]:
    """
    解析目录中的所有 C++ 文件

    参数：
        directory: 目录路径
        extensions: 文件扩展名列表

    返回：
        CppFileInfo 列表
    """
    if extensions is None:
        extensions = ['.cpp', '.h', '.hpp', '.cc', '.cxx', '.hxx', '.c', '.h++']

    parser = CppParser()
    results = []

    path = Path(directory)
    for ext in extensions:
        for file_path in path.rglob(f'*{ext}'):
            info = parser.parse_file(str(file_path))
            if info.classes:
                results.append(info)

    return results

def parse_cpp_file(file_path: str) -> CppFileInfo:
    """
    解析 C++ 文件的便捷函数

    参数：
        file_path: 文件路径

    返回：
        CppFileInfo 对象
    """
    parser = CppParser()
    return parser.parse_file(file_path)
