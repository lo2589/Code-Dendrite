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
    from index.cpp_inheritance.class_indexer import build_class_index

    index = build_class_index("/path/to/project")
    for name, cls in index.classes.items():
        print(f"{name}: {cls.bases}")
"""

from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple

from base.cpp_inheritance.types import CppClassIndex, CppClassInfo, CppMethodInfo
from parse.cpp_inheritance.cpp_parser import parse_cpp_file, parse_cpp_directory, extract_implementation_methods

def resolve_multi_level_inheritance(
    index: CppClassIndex,
    class_name: str,
    max_depth: int = 20
) -> List[Dict]:
    """
    解析多层继承链

    参数：
        index: 类索引
        class_name: 类名
        max_depth: 最大深度

    返回：
        继承链列表，每个元素包含类信息和深度
    """
    result = []
    visited = {}
    depth = 0

    def resolve(name: str, current_depth: int):
        if current_depth >= max_depth or name in visited:
            return

        visited[name] = current_depth

        cls = index.get(name)
        if cls:
            result.append({
                "name": cls.name,
                "file": cls.file,
                "line": cls.line,
                "bases": cls.bases,
                "depth": current_depth,
                "is_template": cls.is_template,
                "is_struct": cls.is_struct
            })

            for base in cls.bases:
                base_name = base.split('::')[-1]
                resolve(base_name, current_depth + 1)

                for full_name, full_cls in index.classes.items():
                    if full_name.split('::')[-1] == base_name and full_name not in visited:
                        resolve(full_name, current_depth + 1)
        else:
            result.append({
                "name": name,
                "file": "[forward_declaration]",
                "line": 0,
                "bases": [],
                "depth": current_depth,
                "is_template": False,
                "is_struct": False
            })

    resolve(class_name, 0)
    return result
