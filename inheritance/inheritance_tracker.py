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
    from inheritance.inheritance_tracker import InheritanceTracker

    tracker = InheritanceTracker("/path/to/project")
    chain = tracker.resolve_inheritance("MyClass")
    mro = tracker.compute_mro("MyClass")
    origin = tracker.find_method_origin("MyClass", "my_method")
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Set

from .types import (
    ClassIndex, ClassEntry, ExternalClassEntry, Location,
    MethodInfo, ClassInfo
)
from .class_indexer import build_class_index
from .resolver import (
    resolve_inheritance, resolve_base_class, compute_mro as _compute_mro,
    find_method_origin as _find_method_origin,
    find_method_origin_with_class
)
from .external_lib import get_builtin_class_info, resolve_external_class


class InheritanceTracker:
    """
    Python 继承追踪器

    封装 resolver.py 中的函数，提供类接口。

    属性：
        root: 项目根目录
        _index: 类索引缓存
        _mro_cache: MRO 缓存
        _external_cache: 外部类缓存
    """

    def __init__(self, root: str):
        """
        初始化继承追踪器

        参数：
            root: 项目根目录路径
        """
        self.root = Path(root)
        self._index: Optional[ClassIndex] = None
        self._mro_cache: Dict[str, List[str]] = {}
        self._external_cache: Dict[str, ExternalClassEntry] = {}

    def _get_index(self) -> ClassIndex:
        """
        获取或构建类索引

        返回：
            ClassIndex: 类索引对象
        """
        if self._index is None:
            self._index = build_class_index(str(self.root))
        return self._index

    def find_class_definition(self, class_name: str) -> Optional[str]:
        """
        查找类的定义位置

        参数：
            class_name: 类名

        返回：
            文件路径，如果未找到返回 None
        """
        index = self._get_index()

        if class_name in index.classes:
            return index.classes[class_name].file

        builtin = get_builtin_class_info(class_name)
        if builtin:
            return f"[builtin:{builtin.module}]"

        return None

    def compute_mro(self, class_name: str) -> List[str]:
        """
        计算方法解析顺序（MRO）

        参数：
            class_name: 类名

        返回：
            MRO 列表，从当前类到根类
        """
        if class_name in self._mro_cache:
            return self._mro_cache[class_name]

        index = self._get_index()
        mro = _compute_mro(class_name, index)

        self._mro_cache[class_name] = mro
        return mro

    def find_method_origin(
        self,
        class_name: str,
        method_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        查找方法在继承链中的定义位置

        参数：
            class_name: 类名
            method_name: 方法名

        返回：
            {
                "class": str,      # 定义方法的类名
                "file": str,       # 文件路径
                "line": int,      # 行号
                "is_override": bool # 是否被覆盖
            }
            如果未找到返回 None
        """
        index = self._get_index()
        result = find_method_origin_with_class(class_name, method_name, index)

        if result:
            return {
                "class": result["class"],
                "file": result["file"],
                "line": result["line"],
                "is_override": result["class"] != class_name
            }

        return None

    def resolve_inheritance(
        self,
        class_name: str,
        max_depth: int = 10
    ) -> List[Dict[str, Any]]:
        """
        解析类的继承链

        参数：
            class_name: 类名
            max_depth: 最大深度，默认 10

        返回：
            继承链列表，每个元素包含：
            {
                "name": str,           # 类名
                "file": str,           # 文件路径
                "line": int,           # 行号
                "bases": List[str],    # 基类列表
                "methods": List[Dict], # 方法列表
                "depth": int,          # 深度
                "is_external": bool,   # 是否是外部库
                "module": str,         # 模块名（外部库）
                "is_builtin": bool,     # 是否是内置类
            }
        """
        index = self._get_index()
        chain = resolve_inheritance(class_name, index, max_depth)

        result = []
        for entry in chain:
            result.append({
                "name": entry.name,
                "file": entry.file,
                "line": entry.line,
                "bases": entry.bases,
                "methods": [
                    {
                        "name": m.name,
                        "start": m.start_line,
                        "end": m.end_line,
                        "has_super": m.has_super
                    }
                    for m in entry.methods
                ] if hasattr(entry, 'methods') else [],
                "depth": getattr(entry, 'depth', 0),
                "is_external": entry.is_external,
                "module": getattr(entry, 'module', None),
                "is_builtin": entry.is_external and entry.file.startswith("[builtin")
            })

        return result

    def resolve_all_bases(self, class_name: str) -> List[str]:
        """
        解析类的所有基类（支持多继承）

        参数：
            class_name: 类名

        返回：
            所有基类列表
        """
        index = self._get_index()

        if class_name not in index.classes:
            return []

        entry = index.classes[class_name]
        return entry.bases

    def find_method_overrides(
        self,
        class_name: str,
        method_name: str
    ) -> List[Dict[str, Any]]:
        """
        查找方法在继承链中被覆盖的情况

        参数：
            class_name: 类名
            method_name: 方法名

        返回：
            覆盖链列表，每个元素包含：
            {
                "class": str,           # 类名
                "file": str,           # 文件路径
                "line": int,           # 行号
                "has_super": bool,     # 是否有 super() 调用
            }
        """
        chain = self.resolve_inheritance(class_name)
        overrides = []

        for entry in chain:
            for method in entry.get("methods", []):
                if method["name"] == method_name:
                    overrides.append({
                        "class": entry["name"],
                        "file": entry["file"],
                        "line": method["start"],
                        "has_super": method["has_super"]
                    })

        return overrides

    def analyze_super_calls(self, class_name: str) -> List[Dict[str, Any]]:
        """
        分析类中所有 super() 调用

        参数：
            class_name: 类名

        返回：
            super() 调用列表，每个元素包含：
            {
                "class": str,           # 调用 super 的类
                "method": str,          # 方法名
                "super_class": str,     # 被调用的父类
                "file": str,            # 文件路径
                "line": int,            # 行号
            }
        """
        chain = self.resolve_inheritance(class_name)
        super_calls = []

        for i, entry in enumerate(chain):
            for method in entry.get("methods", []):
                if method.get("has_super", False):
                    super_class = None
                    if i < len(chain) - 1:
                        super_class = chain[i + 1]["name"]

                    super_calls.append({
                        "class": entry["name"],
                        "method": method["name"],
                        "super_class": super_class,
                        "file": entry["file"],
                        "line": method["start"]
                    })

        return super_calls

    def get_base_class_info(
        self,
        class_name: str,
        base_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取基类的详细信息

        参数：
            class_name: 当前类名
            base_name: 基类名

        返回：
            基类信息，如果未找到返回 None
        """
        index = self._get_index()
        result = resolve_base_class(base_name, class_name, index)

        if result:
            return {
                "name": result.name,
                "is_external": result.is_external,
                "file": result.entry.file if result.entry else None,
                "line": result.entry.line if result.entry else None,
                "bases": result.entry.bases if result.entry else [],
                "module": result.entry.module if result.entry else None
            }

        return None

    def get_inheritance_depth(self, class_name: str) -> int:
        """
        获取继承深度

        参数：
            class_name: 类名

        返回：
            继承深度（不包括当前类）
        """
        mro = self.compute_mro(class_name)
        return len(mro) - 1

    def is_subclass_of(self, class_name: str, base_name: str) -> bool:
        """
        检查是否是某类的子类

        参数：
            class_name: 类名
            base_name: 基类名

        返回：
            如果是子类返回 True
        """
        mro = self.compute_mro(class_name)
        return base_name in mro

    def find_all_subclasses(self, class_name: str) -> List[Dict[str, Any]]:
        """
        查找类的所有子类

        参数：
            class_name: 类名

        返回：
            子类列表，每个元素包含：
            {
                "name": str,           # 类名
                "file": str,           # 文件路径
                "line": int,           # 行号
                "depth": int,           # 继承深度
            }
        """
        index = self._get_index()
        subclasses = []

        def search(name: str, depth: int):
            for entry in index.classes.values():
                if name in entry.bases:
                    subclasses.append({
                        "name": entry.name,
                        "file": entry.file,
                        "line": entry.line,
                        "depth": depth
                    })
                    search(entry.name, depth + 1)

        search(class_name, 1)
        return subclasses

    def get_virtual_methods(self, class_name: str) -> List[Dict[str, Any]]:
        """
        获取类的虚方法列表

        参数：
            class_name: 类名

        返回：
            虚方法列表
        """
        index = self._get_index()

        if class_name not in index.classes:
            return []

        entry = index.classes[class_name]
        virtual_methods = []

        for method in entry.methods:
            if method.is_virtual or method.is_override:
                virtual_methods.append({
                    "name": method.name,
                    "start": method.start_line,
                    "end": method.end_line,
                    "is_virtual": method.is_virtual,
                    "is_override": method.is_override,
                    "has_super": method.has_super
                })

        return virtual_methods

    def export_chain_as_dict(
        self,
        class_name: str,
        max_depth: int = 10
    ) -> Dict[str, Any]:
        """
        导出继承链为字典格式（用于序列化）

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
            "chain": chain,
            "is_builtin": class_name in ["object", "type", "str", "int", "list", "dict"]
        }


def create_tracker(root: str) -> InheritanceTracker:
    """
    创建继承追踪器的便捷函数

    参数：
        root: 项目根目录

    返回：
        InheritanceTracker 实例
    """
    return InheritanceTracker(root)
