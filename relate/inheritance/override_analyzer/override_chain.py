"""
override_analyzer.py - Python 方法覆盖分析器
==============================================
从 TypeScript 迁移的 Python 方法覆盖分析工具。

功能：
- 分析方法在继承链中的覆盖情况
- 构建方法覆盖链
- 检测抽象方法的实现
- 支持 @override 装饰器

用法：
    from relate.inheritance.override_analyzer import (
        build_override_chain,
        find_overridden_method,
        find_abstract_implementations
    )

    overrides = build_override_chain(chain, "my_method")
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set

@dataclass
class OverrideInfo:
    """方法覆盖信息"""
    class_name: str
    method_name: str
    file: str
    line: int
    is_override: bool = False
    is_abstract: bool = False
    has_super_call: bool = False
    decorators: List[str] = field(default_factory=list)

def build_override_chain(
    chain: List[Dict[str, Any]],
    method: str
) -> List[Dict[str, Any]]:
    """
    构建方法覆盖链

    参数：
        chain: 继承链列表（来自 InheritanceTracker.resolve_inheritance）
        method: 方法名

    返回：
        覆盖链列表，每个元素包含：
        {
            "class": str,           # 类名
            "file": str,            # 文件路径
            "line": int,            # 行号
            "has_super": bool,      # 是否有 super() 调用
            "is_override": bool,    # 是否显式覆盖
            "decorators": List[str] # 装饰器列表
        }
    """
    stack = []

    for cls in chain:
        methods = cls.get("methods", [])

        if isinstance(methods, list):
            for m in methods:
                if isinstance(m, dict):
                    if m.get("name") == method:
                        stack.append({
                            "class": cls["name"],
                            "file": cls["file"],
                            "line": m.get("start", 0),
                            "has_super": m.get("has_super", False),
                            "is_override": len(stack) > 0,
                            "decorators": m.get("decorators", [])
                        })
                elif hasattr(m, 'name') and m.name == method:
                    stack.append({
                        "class": cls["name"],
                        "file": cls["file"],
                        "line": m.start_line if hasattr(m, 'start_line') else 0,
                        "has_super": m.has_super,
                        "is_override": len(stack) > 0,
                        "decorators": getattr(m, 'decorators', [])
                    })

    return stack

class OverrideAnalyzer:
    """
    方法覆盖分析器

    用于分析 Python 代码中的方法覆盖情况。
    """

    def __init__(self, chain: List[Dict[str, Any]]):
        """
        初始化分析器

        参数：
            chain: 继承链
        """
        self.chain = chain

    def get_chain(self, method: str) -> List[OverrideInfo]:
        """获取方法的覆盖链"""
        overrides = build_override_chain(self.chain, method)
        return [OverrideInfo(**o) for o in overrides]

    def is_overridden(self, method: str, class_name: str) -> bool:
        """检查方法是否被覆盖"""
        found_class = False

        for cls in self.chain:
            if cls["name"] == class_name:
                found_class = True
                continue

            if found_class:
                methods = cls.get("methods", [])
                for m in methods:
                    method_obj = m if isinstance(m, dict) else m
                    if method_obj.get("name") == method:
                        return True

        return False

    def get_override_count(self, method: str) -> int:
        """获取方法被覆盖的次数"""
        return len([m for m in self.chain if any(
            (isinstance(mo, dict) and mo.get("name") == method) or
            (hasattr(mo, 'name') and mo.name == method)
            for mo in m.get("methods", [])
        )]) - 1

    def find_first_definition(self, method: str) -> Optional[OverrideInfo]:
        """查找方法的第一个定义"""
        for cls in self.chain:
            methods = cls.get("methods", [])
            for m in methods:
                method_obj = m if isinstance(m, dict) else m
                if method_obj.get("name") == method:
                    return OverrideInfo(
                        class_name=cls["name"],
                        method_name=method,
                        file=cls["file"],
                        line=method_obj.get("start", 0)
                    )
        return None

@dataclass
class OverrideChain:
    """方法覆盖链"""
    method_name: str
    root_method: Optional[OverrideInfo]
    overrides: List[OverrideInfo]
    is_complete: bool = True

def detect_override_decorator(chain: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    检测使用 @override 装饰器的方法

    参数：
        chain: 继承链

    返回：
        使用 @override 的方法列表
    """
    overrides = []

    for cls in chain:
        methods = cls.get("methods", [])

        for m in methods:
            method_obj = m if isinstance(m, dict) else m
            decorators = method_obj.get("decorators", [])

            if "override" in decorators or "@override" in decorators:
                overrides.append({
                    "class": cls["name"],
                    "method": method_obj.get("name"),
                    "file": cls["file"],
                    "line": method_obj.get("start", 0)
                })

    return overrides

def find_abstract_implementations(
    class_name: str,
    chain: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    查找抽象方法的实现

    参数：
        class_name: 类名
        chain: 继承链

    返回：
        抽象方法实现列表
    """
    implementations = []
    abstract_methods = set()
    found_class = False

    for cls in chain:
        methods = cls.get("methods", [])

        for m in methods:
            method_obj = m if isinstance(m, dict) else m

            if cls["name"] == class_name:
                found_class = True

            if found_class:
                if not method_obj.get("is_abstract", False):
                    if method_obj.get("name") not in abstract_methods:
                        continue

                    implementations.append({
                        "method": method_obj.get("name"),
                        "class": cls["name"],
                        "file": cls["file"],
                        "line": method_obj.get("start", 0)
                    })
            else:
                if method_obj.get("is_abstract", False):
                    abstract_methods.add(method_obj.get("name"))

    return implementations

def find_overridden_method(
    class_name: str,
    method_name: str,
    chain: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    查找被覆盖的方法定义

    参数：
        class_name: 类名
        method_name: 方法名
        chain: 继承链

    返回：
        被覆盖的方法信息，如果未找到返回 None
    """
    found_current = False

    for cls in chain:
        methods = cls.get("methods", [])

        for m in methods:
            method_obj = m if isinstance(m, dict) else m
            if method_obj.get("name") == method_name:
                if found_current:
                    return {
                        "class": cls["name"],
                        "file": cls["file"],
                        "line": method_obj.get("start", 0),
                        "has_super": method_obj.get("has_super", False)
                    }

        if cls["name"] == class_name:
            found_current = True

    return None

def get_override_depth(
    class_name: str,
    method_name: str,
    chain: List[Dict[str, Any]]
) -> int:
    """
    获取方法的覆盖深度

    参数：
        class_name: 类名
        method_name: 方法名
        chain: 继承链

    返回：
        覆盖深度（0 表示未被覆盖）
    """
    depth = 0
    found_class = False

    for cls in chain:
        if cls["name"] == class_name:
            found_class = True
            continue

        if found_class:
            methods = cls.get("methods", [])
            for m in methods:
                method_obj = m if isinstance(m, dict) else m
                if method_obj.get("name") == method_name:
                    depth += 1

    return depth
