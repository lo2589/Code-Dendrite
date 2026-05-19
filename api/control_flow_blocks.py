from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any, Iterable

from shared.types import Anchor


def _line_end(node: ast.AST) -> int:
    return int(getattr(node, "end_lineno", getattr(node, "lineno", 0)) or 0)


def _source_text(source: str, node: ast.AST) -> str:
    try:
        text = ast.get_source_segment(source, node)
    except Exception:
        text = None
    return " ".join((text or "").strip().split())


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


class _ControlFlowBlockExtractor:
    def __init__(self, root: Path, rel_path: str, source: str) -> None:
        self.root = root
        self.rel_path = rel_path.replace("\\", "/")
        self.source = source
        self.anchors: dict[str, Anchor] = {}
        self._counter = 0

    def extract(self) -> dict[str, Anchor]:
        tree = ast.parse(self.source)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._walk_statements(node.body, self._function_id(node.name))
            elif isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbol = "{}.{}".format(node.name, child.name)
                        self._walk_statements(child.body, self._function_id(symbol))
        return self.anchors

    def _function_id(self, symbol: str) -> str:
        return "{}::{}".format(self.rel_path, symbol)

    def _block_id(self, owner_id: str, kind: str, lineno: int) -> tuple[str, str]:
        self._counter += 1
        suffix = "{}:{}:{}".format(kind, lineno, self._counter)
        block_id = "{}#{}".format(owner_id, suffix)
        symbol = "{}_block_{}".format(kind, self._counter)
        return block_id, symbol

    def _block_hash(self, owner_id: str, kind: str, node: ast.AST, extra: str = "") -> str:
        raw = "{}|{}|{}|{}|{}|{}".format(
            owner_id,
            kind,
            getattr(node, "lineno", 0),
            _line_end(node),
            extra,
            self.rel_path,
        )
        return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]

    def _create_block_anchor(
        self,
        owner_id: str,
        kind: str,
        node: ast.AST,
        symbol: str,
        block_id: str,
        block_metadata: dict[str, Any],
        scope_label: str | None = None,
    ) -> Anchor:
        return Anchor(
            id=block_id,
            symbol=symbol,
            file=self.rel_path,
            line_start=int(getattr(node, "lineno", 0) or 0),
            line_end=_line_end(node),
            hash=self._block_hash(owner_id, kind, node, str(block_metadata)),
            language="python",
            symbol_type="virtual_block",
            is_virtual=True,
            virtual_kind=kind,
            parent_anchor=owner_id,
            scope_label=scope_label,
            block_metadata=block_metadata,
        )

    def _append_calls(
        self,
        anchor: Anchor,
        calls: Iterable[tuple[str, int]],
        scope_label: str,
        seq: int,
        condition: str | None = None,
    ) -> int:
        """将调用列表追加到 anchor.callees，返回下一个可用 seq。"""
        for name, lineno in calls:
            anchor.callees.append({
                "target": name,
                "scope_label": scope_label,
                "condition": condition,
                "is_conditional": bool(condition),
                "seq": seq,
                "line": lineno,
            })
            seq += 1
        return seq

    def _append_child(
        self,
        anchor: Anchor,
        child_id: str,
        scope_label: str,
        seq: int,
        condition: str | None = None,
    ) -> None:
        anchor.callees.append({
            "target": child_id,
            "scope_label": scope_label,
            "condition": condition,
            "is_conditional": bool(condition),
            "seq": seq,
        })

    def _process_branch(
        self,
        body: list[ast.stmt],
        block: Anchor,
        block_id: str,
        scope_label: str,
        condition: str | None,
        seq_start: int,
    ) -> int:
        """按语句顺序处理分支 body，直接调用和子虚拟块交错分配 seq，返回下一个可用 seq。"""
        seq = seq_start
        for stmt in body:
            item_seq = seq
            if isinstance(stmt, ast.If):
                before = set(self.anchors)
                seq = self._handle_if(stmt, block_id, seq)
                for child_id in set(self.anchors) - before:
                    if self.anchors[child_id].parent_anchor == block_id:
                        self._append_child(block, child_id, scope_label, item_seq, condition)
            elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
                before = set(self.anchors)
                seq = self._handle_loop(stmt, block_id, seq)
                for child_id in set(self.anchors) - before:
                    if self.anchors[child_id].parent_anchor == block_id:
                        self._append_child(block, child_id, scope_label, item_seq, condition)
            elif isinstance(stmt, ast.Try):
                before = set(self.anchors)
                seq = self._handle_try(stmt, block_id, seq)
                for child_id in set(self.anchors) - before:
                    if self.anchors[child_id].parent_anchor == block_id:
                        self._append_child(block, child_id, scope_label, item_seq, condition)
            else:
                calls = _collect_stmt_calls(stmt)
                seq = self._append_calls(block, calls, scope_label, seq, condition)
        return seq

    def _walk_statements(self, statements: list[ast.stmt], owner_id: str, seq_start: int = 0) -> int:
        seq = seq_start
        for stmt in statements:
            if isinstance(stmt, ast.If):
                seq = self._handle_if(stmt, owner_id, seq)
            elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
                seq = self._handle_loop(stmt, owner_id, seq)
            elif isinstance(stmt, ast.Try):
                seq = self._handle_try(stmt, owner_id, seq)
        return seq

    def _handle_if(self, node: ast.If, owner_id: str, seq_start: int = 0) -> int:
        block_id, symbol = self._block_id(owner_id, "cond", int(getattr(node, "lineno", 0) or 0))

        cases: list[tuple[str, str, list[ast.stmt]]] = []
        current = node
        cases.append(("case:0", _source_text(self.source, current.test), current.body))
        idx = 1
        default_body: list[ast.stmt] = []
        while current.orelse:
            if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
                current = current.orelse[0]
                cases.append(("case:{}".format(idx), _source_text(self.source, current.test), current.body))
                idx += 1
            else:
                default_body = current.orelse
                break

        block = self._create_block_anchor(
            owner_id,
            "condition",
            node,
            symbol,
            block_id,
            {
                "cases": [
                    {"scope_label": label, "condition": cond}
                    for label, cond, _ in cases
                ],
                "has_default": bool(default_body),
            },
        )

        # 所有分支并列从 seq_start 开始，各自顺延，取最大值
        max_seq = seq_start
        for label, condition, body in cases:
            branch_end = self._process_branch(body, block, block_id, label, condition, seq_start)
            max_seq = max(max_seq, branch_end)

        if default_body:
            branch_end = self._process_branch(default_body, block, block_id, "default", None, seq_start)
            max_seq = max(max_seq, branch_end)

        self.anchors[block_id] = block
        return max_seq

    def _handle_loop(self, node: ast.AST, owner_id: str, seq_start: int = 0) -> int:
        block_id, symbol = self._block_id(owner_id, "loop", int(getattr(node, "lineno", 0) or 0))
        if isinstance(node, ast.While):
            expr = _source_text(self.source, node.test)
            loop_kind = "while"
        else:
            expr = "{} in {}".format(
                _source_text(self.source, node.target),
                _source_text(self.source, node.iter),
            )
            loop_kind = "for"

        block = self._create_block_anchor(
            owner_id,
            "loop",
            node,
            symbol,
            block_id,
            {"loop_kind": loop_kind, "expr": expr},
        )

        # body 先顺序排，orelse 接 body 末尾（loop 不 break 才执行）
        body_end = self._process_branch(node.body, block, block_id, "body", None, seq_start)

        if getattr(node, "orelse", None):
            orelse_end = self._process_branch(node.orelse, block, block_id, "orelse", None, body_end)
            final_seq = orelse_end
        else:
            final_seq = body_end

        self.anchors[block_id] = block
        return final_seq

    def _handle_try(self, node: ast.Try, owner_id: str, seq_start: int = 0) -> int:
        block_id, symbol = self._block_id(owner_id, "try", int(getattr(node, "lineno", 0) or 0))
        metadata: dict[str, Any] = {
            "handlers": [],
            "has_else": bool(node.orelse),
            "has_finally": bool(node.finalbody),
        }
        block = self._create_block_anchor(owner_id, "try", node, symbol, block_id, metadata)

        # body 先执行
        body_end = self._process_branch(node.body, block, block_id, "body", None, seq_start)

        # handlers 和 orelse 并列（互斥：有异常走 handler，无异常走 orelse）
        max_handler_seq = body_end
        for idx, handler in enumerate(node.handlers):
            scope_label = "case:{}".format(idx)
            exc_name = _source_text(self.source, handler.type) if handler.type else "Exception"
            block.block_metadata["handlers"].append({"scope_label": scope_label, "exception": exc_name})
            handler_end = self._process_branch(handler.body, block, block_id, scope_label, exc_name, body_end)
            max_handler_seq = max(max_handler_seq, handler_end)

        if node.orelse:
            orelse_end = self._process_branch(node.orelse, block, block_id, "else", None, body_end)
            max_handler_seq = max(max_handler_seq, orelse_end)

        # finally 一定执行，排在所有分支之后
        if node.finalbody:
            finally_end = self._process_branch(node.finalbody, block, block_id, "finally", None, max_handler_seq)
            final_seq = finally_end
        else:
            final_seq = max_handler_seq

        self.anchors[block_id] = block
        return final_seq


def extract_control_flow_blocks(root: str = ".") -> dict[str, Anchor]:
    import os
    from shared.codedendrite_ignore import CodeDendriteIgnore
    root_path = Path(root)
    ignore = CodeDendriteIgnore(str(root_path))
    result: dict[str, Anchor] = {}
    for dirpath, dirnames, filenames in os.walk(root_path):
        dp = Path(dirpath)
        dirnames[:] = [d for d in dirnames if ignore.should_scan(dp / d / "_x.py")]
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            py_file = dp / fname
            if not ignore.should_scan(py_file):
                continue
            try:
                rel_path = str(py_file.relative_to(root_path)).replace("\\", "/")
                source = py_file.read_text(encoding="utf-8", errors="replace")
                result.update(_ControlFlowBlockExtractor(root_path, rel_path, source).extract())
            except Exception:
                continue
    return result
