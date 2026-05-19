"""
cpp_tracker.py - C++ 继承追踪封装类
====================================
C++ 继承追踪的统一接口，支持：
- 普通类和模板类
- 多继承
- 结构体
- 命名空间

用法：
    from cpp_inheritance.cpp_tracker import CppInheritanceTracker

    tracker = CppInheritanceTracker("/path/to/project")
    chain = tracker.resolve_inheritance("MyClass")
    mro = tracker.compute_mro("MyClass")
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from .types import CppClassIndex, CppClassInfo, CppLocation
from .class_indexer import (
    build_class_index, get_class_hierarchy,
    find_subclasses, get_all_virtual_methods,
    resolve_multi_level_inheritance
)
from .resolver import (
    resolve_inheritance, compute_mro, compute_full_mro,
    find_method_origin, get_override_chain, get_virtual_methods,
    is_subclass_of, get_all_bases, find_common_base
)


class CppInheritanceTracker:
    """
    C++ 继承追踪器

    提供统一的接口来追踪 C++ 类的继承关系。
    """

    def __init__(self, root: str):
        """
        初始化追踪器

        参数：
            root: 项目根目录
        """
        self.root = Path(root)
        self._index: Optional[CppClassIndex] = None

    def _get_index(self) -> CppClassIndex:
        """获取或构建类索引"""
        if self._index is None:
            self._index = build_class_index(str(self.root))
        return self._index

    def find_class_definition(self, class_name: str) -> Optional[str]:
        """
        查找类的定义位置

        参数：
            class_name: 类名

        返回：
            文件路径
        """
        index = self._get_index()
        cls = index.get(class_name)

        if cls:
            return cls.file

        for c in index.values():
            if c.name.endswith(f"::{class_name}"):
                return c.file

        return None

    def resolve_inheritance(
        self,
        class_name: str,
        max_depth: int = 20
    ) -> List[Dict[str, Any]]:
        """
        解析类的继承链

        参数：
            class_name: 类名
            max_depth: 最大深度

        返回：
            继承链列表
        """
        index = self._get_index()
        chain = resolve_inheritance(index, class_name, max_depth)

        return [
            {
                "name": entry.name,
                "file": entry.file,
                "line": entry.line,
                "bases": entry.bases,
                "methods": [
                    {
                        "name": m.name,
                        "start": m.start_line,
                        "end": m.end_line,
                        "is_virtual": m.is_virtual,
                        "is_override": m.is_override,
                        "is_pure_virtual": m.is_pure_virtual,
                        "is_const": m.is_const,
                        "access": m.access
                    }
                    for m in entry.methods
                ],
                "depth": entry.depth,
                "is_external": entry.is_external
            }
            for entry in chain
        ]

    def compute_mro(self, class_name: str) -> List[str]:
        """
        计算方法解析顺序

        参数：
            class_name: 类名

        返回：
            MRO 列表
        """
        index = self._get_index()
        return compute_mro(index, class_name)

    def find_method_origin(
        self,
        class_name: str,
        method_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        查找方法定义位置

        参数：
            class_name: 类名
            method_name: 方法名

        返回：
            方法定义位置
        """
        index = self._get_index()
        location = find_method_origin(index, class_name, method_name)

        if location:
            return {
                "file": location.file,
                "line": location.line
            }

        return None

    def get_override_chain(
        self,
        class_name: str,
        method_name: str
    ) -> List[Dict[str, Any]]:
        """
        获取方法覆盖链

        参数：
            class_name: 类名
            method_name: 方法名

        返回：
            覆盖链列表
        """
        index = self._get_index()
        return get_override_chain(index, class_name, method_name)

    def get_virtual_methods(self, class_name: str) -> List[Dict[str, Any]]:
        """
        获取虚方法列表

        参数：
            class_name: 类名

        返回：
            虚方法列表
        """
        index = self._get_index()
        return get_virtual_methods(index, class_name)

    def is_subclass_of(
        self,
        class_name: str,
        base_name: str
    ) -> bool:
        """
        检查是否是某类的子类

        参数：
            class_name: 类名
            base_name: 基类名

       返回：
            如果是子类返回 True
        """
        index = self._get_index()
        return is_subclass_of(index, class_name, base_name)

    def get_all_bases(self, class_name: str) -> List[str]:
        """
        获取所有基类（多继承）

        参数：
            class_name: 类名

        返回：
            基类列表
        """
        index = self._get_index()
        return get_all_bases(index, class_name)

    def find_common_base(
        self,
        class1: str,
        class2: str
    ) -> Optional[str]:
        """
        查找两个类的共同基类

        参数：
            class1: 类1
            class2: 类2

        返回：
            共同基类
        """
        index = self._get_index()
        return find_common_base(index, class1, class2)

    def find_subclasses(self, class_name: str) -> List[Dict[str, Any]]:
        """
        查找类的所有子类

        参数：
            class_name: 类名

        返回：
            子类列表
        """
        index = self._get_index()
        subclasses = find_subclasses(index, class_name)

        return [
            {
                "name": cls.name,
                "file": cls.file,
                "line": cls.line,
                "bases": cls.bases
            }
            for cls in subclasses
        ]

    def get_inheritance_depth(self, class_name: str) -> int:
        """
        获取继承深度

        参数：
            class_name: 类名

        返回：
            继承深度
        """
        mro = self.compute_mro(class_name)
        return len(mro) - 1

    def export_chain_as_dict(
        self,
        class_name: str,
        max_depth: int = 20
    ) -> Dict[str, Any]:
        """
        导出继承链为字典

        参数：
            class_name: 类名
            max_depth: 最大深度

        返回：
            继承链字典
        """
        chain = self.resolve_inheritance(class_name, max_depth)
        mro = self.compute_mro(class_name)

        return {
            "class_name": class_name,
            "mro": mro,
            "depth": len(chain),
            "chain": chain
        }

    def resolve_multi_level_inheritance(
        self,
        class_name: str,
        max_depth: int = 20
    ) -> List[Dict[str, Any]]:
        """
        解析多层继承链（完整版本）

        与 resolve_inheritance 不同，这个方法会追踪所有基类，
        包括多继承中的所有路径。

        参数：
            class_name: 类名
            max_depth: 最大深度

        返回：
            继承链列表，每个元素包含：
            {
                "name": str,           # 类名
                "file": str,           # 文件路径
                "line": int,           # 行号
                "bases": List[str],    # 基类列表
                "depth": int,          # 继承深度
                "is_template": bool,   # 是否是模板类
                "is_struct": bool      # 是否是结构体
            }
        """
        index = self._get_index()
        return resolve_multi_level_inheritance(index, class_name, max_depth)

    def get_full_inheritance_tree(
        self,
        class_name: str,
        max_depth: int = 20
    ) -> Dict[str, Any]:
        """
        获取完整的继承树

        参数：
            class_name: 类名
            max_depth: 最大深度

        返回：
            继承树字典
        """
        chain = self.resolve_multi_level_inheritance(class_name, max_depth)
        hierarchy = self.get_class_hierarchy(class_name)

        return {
            "class_name": class_name,
            "chain": chain,
            "hierarchy": hierarchy,
            "total_depth": len(hierarchy) - 1,
            "base_count": len(chain[0]["bases"]) if chain else 0
        }

    def get_class_hierarchy(self, class_name: str) -> List[str]:
        """
        获取类的继承层次

        参数：
            class_name: 类名

        返回：
            继承层次列表
        """
        index = self._get_index()
        return get_class_hierarchy(index, class_name)


def create_tracker(root: str) -> CppInheritanceTracker:
    """
    创建追踪器的便捷函数

    参数：
        root: 项目根目录

    返回：
        CppInheritanceTracker 实例
    """
    return CppInheritanceTracker(root)
