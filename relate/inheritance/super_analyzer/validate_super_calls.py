"""
super_analyzer.py - Python super() 调用分析器
==============================================
从 TypeScript 迁移的 Python super() 调用分析工具。

功能：
- 分析类继承链中所有 super() 调用
- 追踪 super() 调用的参数和目标
- 验证 super() 调用的正确性

用法：
    from relate.inheritance.super_analyzer import analyze_super_calls, find_super_in_method

    calls = analyze_super_calls(chain)
    method_calls = find_super_in_method(file_path, class_name, method_name)
"""

import ast
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
from pathlib import Path

def validate_super_calls(chain: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    验证继承链中 super() 调用的正确性

    参数：
        chain: 继承链列表

    返回：
        验证结果列表，包含错误和警告
    """
    issues = []

    for i, entry in enumerate(chain):
        for method in entry.get("methods", []):
            if not method.get("has_super", False):
                continue

            if i >= len(chain) - 1:
                issues.append({
                    "type": "error",
                    "class": entry["name"],
                    "method": method["name"],
                    "message": f"类 {entry['name']} 调用 super() 但没有父类"
                })

            if method.get("has_super"):
                parent_class = chain[i + 1]["name"] if i < len(chain) - 1 else None
                if parent_class and method["name"].startswith("__"):
                    issues.append({
                        "type": "warning",
                        "class": entry["name"],
                        "method": method["name"],
                        "message": f"在 {entry['name']}.{method['name']} 中使用 super() 调用 dunder 方法"
                    })

    return issues
