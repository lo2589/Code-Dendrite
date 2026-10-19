from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any, Iterable

from analyzer.shared.types import Anchor

def _line_end(node: ast.AST) -> int:
    return int(getattr(node, "end_lineno", getattr(node, "lineno", 0)) or 0)

def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return "{}.{}".format(base, node.attr) if base else node.attr
    return ""

class _DirectCallCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []  # (name, lineno)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        if name:
            self.calls.append((name, getattr(node, "lineno", 0)))
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        return

    def visit_For(self, node: ast.For) -> None:
        return

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        return

    def visit_While(self, node: ast.While) -> None:
        return

    def visit_Try(self, node: ast.Try) -> None:
        return

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

def _collect_stmt_calls(stmt: ast.stmt) -> list[tuple[str, int]]:
    """收集单条语句中的直接调用（不递归进控制流），返回 (name, lineno) 列表，保留重复。"""
    collector = _DirectCallCollector()
    collector.visit(stmt)
    return collector.calls

def _source_text(source: str, node: ast.AST) -> str:
    try:
        text = ast.get_source_segment(source, node)
    except Exception:
        text = None
    return " ".join((text or "").strip().split())
