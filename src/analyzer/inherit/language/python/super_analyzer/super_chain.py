"""
super_analyzer.py - Python super() 调用分析器
==============================================
从 TypeScript 迁移的 Python super() 调用分析工具。

功能：
- 分析类继承链中所有 super() 调用
- 追踪 super() 调用的参数和目标
- 验证 super() 调用的正确性

用法：
    from analyzer.inherit.language.python.super_analyzer import analyze_super_calls, find_super_in_method

    calls = analyze_super_calls(chain)
    method_calls = find_super_in_method(file_path, class_name, method_name)
"""

import ast
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
from pathlib import Path

@dataclass
class SuperCallInfo:
    """super() 调用信息"""
    class_name: str
    method_name: str
    super_class_name: Optional[str]
    file: str
    line: int
    column: int
    super_args: List[str] = field(default_factory=list)
    call_type: str = "implicit"

class SuperAnalyzer:
    """
    super() 调用分析器

    用于分析 Python 代码中 super() 的使用情况。
    """

    def __init__(self, project_root: Optional[str] = None):
        """
        初始化分析器

        参数：
            project_root: 项目根目录
        """
        self.project_root = Path(project_root) if project_root else None

    def analyze_file(self, file_path: str) -> List[SuperCallInfo]:
        """
        分析文件中的所有 super() 调用

        参数：
            file_path: Python 文件路径

        返回：
            super() 调用列表
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()

        tree = ast.parse(source)
        return self._analyze_tree(tree, file_path)

    def _analyze_tree(self, tree: ast.AST, file_path: str) -> List[SuperCallInfo]:
        """分析 AST 树中的 super() 调用"""
        calls = []

        class SuperVisitor(ast.NodeVisitor):
            def __init__(self, current_class=None, current_method=None):
                self.current_class = current_class
                self.current_method = current_method
                self.calls = []

            def visit_ClassDef(self, node: ast.ClassDef):
                old_class = self.current_class
                self.current_class = node.name
                self.generic_visit(node)
                self.current_class = old_class

            def visit_FunctionDef(self, node: ast.FunctionDef):
                if self.current_class:
                    old_method = self.current_method
                    self.current_method = node.name

                    for child in ast.walk(node):
                        if isinstance(child, ast.Call):
                            if self._is_super_call(child):
                                super_info = self._extract_super_info(
                                    child, node, file_path, self.current_class
                                )
                                self.calls.append(super_info)

                    self.current_method = old_method

                self.generic_visit(node)

            def _is_super_call(self, node: ast.Call) -> bool:
                if isinstance(node.func, ast.Name):
                    return node.func.id == 'super'
                if isinstance(node.func, ast.Attribute):
                    return node.func.attr == 'super'
                return False

            def _extract_super_info(
                self,
                call: ast.Call,
                func: ast.FunctionDef,
                file_path: str,
                class_name: str
            ) -> SuperCallInfo:
                super_args = []
                call_type = "implicit"

                if call.args:
                    for arg in call.args:
                        if isinstance(arg, ast.Name):
                            super_args.append(arg.id)
                        elif isinstance(arg, ast.Constant):
                            super_args.append(str(arg.value))
                        elif isinstance(arg, ast.Attribute):
                            super_args.append(ast.unparse(arg))

                if call.keywords:
                    for kw in call.keywords:
                        if kw.arg == 'type':
                            super_args.append(f"type={ast.unparse(kw.value)}")
                        elif kw.arg == 'first':
                            super_args.append(f"first={ast.unparse(kw.value)}")

                if len(call.args) >= 2 or any(kw.arg in ['type', 'first'] for kw in call.keywords):
                    call_type = "explicit"

                return SuperCallInfo(
                    class_name=class_name,
                    method_name=func.name,
                    super_class_name=self._infer_super_class(call, super_args),
                    file=file_path,
                    line=call.lineno,
                    column=call.col_offset,
                    super_args=super_args,
                    call_type=call_type
                )

            def _infer_super_class(self, call: ast.Call, args: List[str]) -> Optional[str]:
                if len(args) >= 2:
                    return args[0]
                return None

        visitor = SuperVisitor()
        visitor.visit(tree)
        return visitor.calls

@dataclass
class SuperChain:
    """super() 调用链"""
    root_class: str
    root_method: str
    calls: List[SuperCallInfo]

def analyze_super_calls(chain: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    分析继承链中所有 super() 调用

    参数：
        chain: 继承链列表（来自 InheritanceTracker.resolve_inheritance）

    返回：
        super() 调用列表，每个元素包含：
        {
            "class": str,           # 调用 super 的类
            "method": str,          # 方法名
            "super_class": str,     # 被调用的父类
            "file": str,            # 文件路径
            "line": int,            # 行号
            "call_type": str,       # "implicit" 或 "explicit"
        }
    """
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
                    "line": method["start"],
                    "call_type": "implicit" if method.get("has_super") else "explicit"
                })

    return super_calls

def build_super_chain(
    root_class: str,
    root_method: str,
    chain: List[Dict[str, Any]]
) -> SuperChain:
    """
    构建 super() 调用链

    参数：
        root_class: 根类名
        root_method: 根方法名
        chain: 继承链

    返回：
        SuperChain 对象
    """
    calls = []

    for i, entry in enumerate(chain):
        for method in entry.get("methods", []):
            if method["name"] == root_method:
                super_class = None
                if i < len(chain) - 1:
                    super_class = chain[i + 1]["name"]

                calls.append(SuperCallInfo(
                    class_name=entry["name"],
                    method_name=method["name"],
                    super_class_name=super_class,
                    file=entry["file"],
                    line=method["start"],
                    column=0,
                    call_type="implicit"
                ))

    return SuperChain(
        root_class=root_class,
        root_method=root_method,
        calls=calls
    )

def find_super_in_method(
    file_path: str,
    class_name: str,
    method_name: str
) -> List[Dict[str, Any]]:
    """
    查找方法中的 super() 调用

    参数：
        file_path: Python 文件路径
        class_name: 类名
        method_name: 方法名

    返回：
        super() 调用列表
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        source = f.read()

    tree = ast.parse(source)
    calls = []

    class MethodSuperFinder(ast.NodeVisitor):
        def __init__(self):
            self.in_target_class = False
            self.in_target_method = False
            self.calls = []

        def visit_ClassDef(self, node: ast.ClassDef):
            if node.name == class_name:
                self.in_target_class = True
                self.generic_visit(node)
                self.in_target_class = False
            else:
                self.generic_visit(node)

        def visit_FunctionDef(self, node: ast.FunctionDef):
            if self.in_target_class and node.name == method_name:
                self.in_target_method = True
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Name) and child.func.id == 'super':
                            super_args = [ast.unparse(arg) for arg in child.args]
                            self.calls.append({
                                "line": child.lineno,
                                "column": child.col_offset,
                                "args": super_args,
                                "type": "implicit" if not child.args else "explicit"
                            })
                self.in_target_method = False
            self.generic_visit(node)

    finder = MethodSuperFinder()
    finder.visit(tree)
    return finder.calls
