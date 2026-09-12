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
    from analyzer.inherit.language.python.override_analyzer import (
        build_override_chain,
        find_overridden_method,
        find_abstract_implementations
    )

    overrides = build_override_chain(chain, "my_method")
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set

def validate_overrides(
    class_name: str,
    chain: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    验证方法覆盖的正确性

    参数：
        class_name: 类名
        chain: 继承链

    返回：
        验证问题列表
    """
    issues = []
    parent_methods: Set[str] = set()
    found_class = False

    for cls in chain:
        if cls["name"] == class_name:
            found_class = True
            continue

        if not found_class:
            methods = cls.get("methods", [])
            for m in methods:
                method_obj = m if isinstance(m, dict) else m
                parent_methods.add(method_obj.get("name"))

    if found_class:
        for cls in chain:
            if cls["name"] != class_name:
                break

            methods = cls.get("methods", [])
            for m in methods:
                method_obj = m if isinstance(m, dict) else m
                method_name = method_obj.get("name")

                if method_name in parent_methods:
                    if not method_obj.get("has_super", False):
                        issues.append({
                            "type": "warning",
                            "class": class_name,
                            "method": method_name,
                            "message": f"方法 {method_name} 覆盖了父类方法但没有调用 super()"
                        })

    return issues
