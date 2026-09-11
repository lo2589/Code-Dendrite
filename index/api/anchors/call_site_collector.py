"""
锚点管理接口层
========================
generate_all_anchors: 从 5 个源 merge，写入 .codedendrite/anchors.json
load_anchors / get_anchor: 唯一读取接口
"""

import json
import os
import ast
import re as _re
from dataclasses import asdict
from pathlib import Path
from typing import Optional, List, Dict

from base.shared.types import Anchor
from base.shared.codedendrite_ignore import CodeDendriteIgnore
from base.shared.formula_skip import should_skip as _should_skip_formula

_EMBED_STYLE_RE = _re.compile(r'<style[^>]*>(.*?)</style>', _re.DOTALL | _re.IGNORECASE)
_EMBED_SCRIPT_RE = _re.compile(r'<script[^>]*>(.*?)</script>', _re.DOTALL | _re.IGNORECASE)
_EMBED_DOM_ID_RE = _re.compile(r'\bid=["\']([A-Za-z][\w-]*)["\']')
_EMBED_CSS_SEL_RE = _re.compile(r'(?:^|[\s,>+~])([.#][A-Za-z][\w-]*)', _re.MULTILINE)
_EMBED_JS_FUNC_RE = _re.compile(r'function\s+([A-Za-z$_][\w$]*)\s*\(')
_EMBED_JS_QUERY_RE = _re.compile(r'(?:querySelectorAll?|getElementById)\s*\(\s*["\']([^"\']+)["\']')

# ── 调试日志（环境变量 CD_ANCHOR_LOG 开关；默认不打，不污染生产 run）──
import time as _time
_ANCHOR_DBG = bool(os.environ.get("CD_ANCHOR_LOG"))

from index.api.anchors.subscript_string import _subscript_string

def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""

def _config_path(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        try:
            text = ast.unparse(node)
        except Exception:
            return ""
        for root in ("cfg.", "config."):
            if text.startswith(root):
                return text[len(root):]
        if text.startswith("self.cfg."):
            return text[len("self.cfg."):]
    if isinstance(node, ast.Call) and _call_name(node.func) == "_choice":
        parts = [
            str(arg.value)
            for arg in node.args[1:3]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
        ]
        if len(parts) == 2:
            return ".".join(parts)
    return ""

def _factory_selector(node: ast.AST) -> dict:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {"factory_key": node.value}
    path = _config_path(node)
    if path:
        return {"factory_config_paths": [path]}
    template, paths = _fstring_template(node)
    if template:
        result = {"factory_template": template}
        if paths:
            result["factory_config_paths"] = paths
        return result
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format"
        and isinstance(node.func.value, ast.Constant)
        and isinstance(node.func.value.value, str)
    ):
        template = _re.sub(r"\{[^}]*\}", "*", node.func.value.value)
        if "*" in template:
            return {"factory_template": template}
    return {}

def _fstring_template(node: ast.AST) -> tuple[str, list[str]]:
    if not isinstance(node, ast.JoinedStr):
        return "", []
    parts = []
    config_paths = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
        elif isinstance(value, ast.FormattedValue):
            parts.append("*")
            path = _config_path(value.value)
            if path and path not in config_paths:
                config_paths.append(path)
    template = "".join(parts)
    return (template, config_paths) if "*" in template else ("", [])

class _CallSiteCollector(ast.NodeVisitor):
    def __init__(self, import_aliases: Optional[dict] = None) -> None:
        self.call_sites: list[dict] = []
        self.conds: list[dict] = []
        self.seq = 0
        self.import_aliases = import_aliases or {}
        self.variable_types: dict[str, set[str]] = {}

    def _expr(self, node: ast.AST | None) -> str:
        if node is None:
            return "else"
        try:
            return ast.unparse(node)
        except Exception:
            return ""

    def _cond_item(self, cond_id: str, expr: str) -> dict:
        return {cond_id: expr or "else"}

    def _append_call(self, node: ast.Call) -> None:
        registry_key = _subscript_string(node.func)
        registry_template, config_paths = (
            _fstring_template(node.func.slice)
            if isinstance(node.func, ast.Subscript) else ("", [])
        )
        target = registry_key or registry_template or _call_name(node.func)
        if not target:
            return
        site = {
            "target": target,
            "seq": self.seq,
            "line": int(getattr(node, "lineno", 0) or 0),
            "conds": list(self.conds) if self.conds else ["nocond"],
            "call_kind": "name",
        }
        if registry_key and isinstance(node.func, ast.Subscript):
            site["call_kind"] = "registry"
            site["receiver"] = self._expr(node.func.value)
            site["registry_key"] = registry_key
        elif registry_template and isinstance(node.func, ast.Subscript):
            site["call_kind"] = "registry_template"
            site["receiver"] = self._expr(node.func.value)
            site["registry_template"] = registry_template
            if config_paths:
                site["config_paths"] = config_paths
            import_ref = self.import_aliases.get(site["receiver"])
            if import_ref:
                site["registry_name"] = str(import_ref.get("imported") or "")
        elif isinstance(node.func, ast.Attribute):
            site["call_kind"] = "attribute"
            site["receiver"] = self._expr(node.func.value)
            receiver_types = sorted(self.variable_types.get(site["receiver"], set()))
            if receiver_types:
                site["receiver_types"] = receiver_types
            import_ref = self.import_aliases.get(site["receiver"])
            if import_ref:
                site["import_ref"] = dict(import_ref)
        if _call_name(node.func) == "create" and node.args:
            site.update(_factory_selector(node.args[0]))
        self.call_sites.append(site)
        self.seq += 1

    def visit_Subscript(self, node: ast.Subscript) -> None:
        template, config_paths = _fstring_template(node.slice)
        if template:
            receiver = self._expr(node.value)
            site = {
                "target": template,
                "seq": self.seq,
                "line": int(getattr(node, "lineno", 0) or 0),
                "conds": list(self.conds) if self.conds else ["nocond"],
                "call_kind": "registry_template",
                "receiver": receiver,
                "registry_reference": True,
                "registry_template": template,
            }
            if config_paths:
                site["config_paths"] = config_paths
            import_ref = self.import_aliases.get(receiver)
            if import_ref:
                site["registry_name"] = str(import_ref.get("imported") or "")
            self.call_sites.append(site)
            self.seq += 1
            self.visit(node.value)
            for value in getattr(node.slice, "values", []):
                if isinstance(value, ast.FormattedValue):
                    self.visit(value.value)
            return
        self.generic_visit(node)

    def _remember_assignment_type(self, target: ast.AST, value: ast.AST) -> None:
        if not isinstance(target, ast.Name) or not isinstance(value, ast.Call):
            return
        constructor = _call_name(value.func)
        if constructor:
            self.variable_types.setdefault(target.id, set()).add(constructor)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._remember_assignment_type(target, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self._remember_assignment_type(node.target, node.value)
        self.generic_visit(node)

    @staticmethod
    def _is_super_call(node: ast.AST) -> bool:
        return (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "super")

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        # super().method() or super(Cls, self).method() — emit super::method,
        # suppress the inner super() so it doesn't appear as a bare noise call
        if isinstance(func, ast.Attribute) and self._is_super_call(func.value):
            self.call_sites.append({
                "target": "super::{}".format(func.attr),
                "seq": self.seq,
                "line": int(getattr(node, "lineno", 0) or 0),
                "conds": list(self.conds) if self.conds else ["nocond"],
            })
            self.seq += 1
            # Visit args of the outer call but skip the super() sub-call itself
            for child in node.args:
                self.visit(child)
            for kw in node.keywords:
                self.visit(kw.value)
            return
        self._append_call(node)
        if isinstance(node.func, ast.Subscript) and _fstring_template(node.func.slice)[0]:
            self.visit(node.func.value)
            for child in node.args:
                self.visit(child)
            for kw in node.keywords:
                self.visit(kw.value)
        else:
            self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        cond_id = "if:{}".format(int(getattr(node, "lineno", 0) or 0))
        current = node
        while True:
            self.conds.append(self._cond_item(cond_id, self._expr(current.test)))
            for stmt in current.body:
                self.visit(stmt)
            self.conds.pop()
            if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
                current = current.orelse[0]
                continue
            if current.orelse:
                self.conds.append(self._cond_item(cond_id, "else"))
                for stmt in current.orelse:
                    self.visit(stmt)
                self.conds.pop()
            break

    def visit_For(self, node: ast.For) -> None:
        self._visit_loop(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._visit_loop(node)

    def visit_While(self, node: ast.While) -> None:
        cond_id = "while:{}".format(int(getattr(node, "lineno", 0) or 0))
        self.conds.append(self._cond_item(cond_id, self._expr(node.test)))
        for stmt in node.body:
            self.visit(stmt)
        self.conds.pop()
        if node.orelse:
            self.conds.append(self._cond_item(cond_id, "else"))
            for stmt in node.orelse:
                self.visit(stmt)
            self.conds.pop()

    def _visit_loop(self, node: ast.AST) -> None:
        cond_id = "for:{}".format(int(getattr(node, "lineno", 0) or 0))
        expr = "{} in {}".format(self._expr(getattr(node, "target", None)), self._expr(getattr(node, "iter", None)))
        self.conds.append(self._cond_item(cond_id, expr))
        for stmt in getattr(node, "body", []):
            self.visit(stmt)
        self.conds.pop()
        if getattr(node, "orelse", None):
            self.conds.append(self._cond_item(cond_id, "else"))
            for stmt in node.orelse:
                self.visit(stmt)
            self.conds.pop()

    def visit_Try(self, node: ast.Try) -> None:
        try_id = "try:{}".format(int(getattr(node, "lineno", 0) or 0))
        self.conds.append(self._cond_item(try_id, "try"))
        for stmt in node.body:
            self.visit(stmt)
        self.conds.pop()
        for handler in node.handlers:
            expr = self._expr(handler.type) if handler.type else "except"
            self.conds.append(self._cond_item(try_id, expr))
            for stmt in handler.body:
                self.visit(stmt)
            self.conds.pop()
        if node.orelse:
            self.conds.append(self._cond_item(try_id, "else"))
            for stmt in node.orelse:
                self.visit(stmt)
            self.conds.pop()
        if node.finalbody:
            self.conds.append(self._cond_item(try_id, "finally"))
            for stmt in node.finalbody:
                self.visit(stmt)
            self.conds.pop()

    def generic_visit(self, node) -> None:
        # 跳公式：不下钻进大的纯数据/公式子树（sqrt/S 那种不是调用关系，是数据）
        for child in ast.iter_child_nodes(node):
            if _should_skip_formula(child):
                continue
            self.visit(child)

__all__ = [
    "list_all_symbols",
    "list_anchors",
    "create_anchor",
    "check_all_anchors",
    "generate_all_anchors",
    "update_anchors_for_files",
    "load_anchors",
    "get_anchor",
    "search_anchors",
    "filter_anchors_by_file",
    "list_anchors_in_file",
]

def _alog(msg: str):
    if _ANCHOR_DBG:
        print(f"[anchors {_time.strftime('%H:%M:%S')}] {msg}", flush=True)
