"""
tracer.py — PathTracer 核心

实现链式调用接口：
    tracer.from_entry(fn).given(k, v).until(target).run()

追踪策略：
  1. 从锚点数据库加载调用图
  2. given() 条件在分叉点剪枝（丢弃不满足条件的分支）
  3. until() 找到目标节点时停止展开
  4. for 循环只分析“一次迭代语义”，不展开 N 次
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
from collections import deque

from relate.pathTracer.node import PipelineNode
from relate.pathTracer.result import TraceResult


class PathTracer:
    """
    管线路径追踪器。

    参数：
        project_root: 项目根目录
        anchors_path: anchors.json 路径
        max_depth:    最大追踪深度（防止无限递归）
    """

    def __init__(
        self,
        project_root: str,
        anchors_path: Optional[str] = None,
        max_depth: int = 20,
    ):
        self.root = Path(project_root)
        self.anchors_path = Path(anchors_path) if anchors_path else (
            self.root / ".codedendrite" / "anchors.json"
        )
        self.max_depth = max_depth

        self._anchors: dict = {}
        self._call_graph: dict[str, list[str]] = {}
        self._loaded = False

        # 链式调用状态
        self._entry: Optional[str] = None
        self._conditions: dict = {}
        self._target: Optional[str] = None

    # ── 链式调用接口 ─────────────────────────────────────────

    def from_entry(self, function_name: str) -> "PathTracer":
        """设置追踪起点。"""
        self._entry = function_name
        self._conditions = {}
        self._target = None
        return self

    def given(self, variable: str, value) -> "PathTracer":
        """
        添加已知条件（用于分叉点剪枝）。

        示例：
            .given("request.type", "A")
            .given("user.is_admin", False)
        """
        self._conditions[variable] = value
        return self

    def until(self, target_function: str) -> "PathTracer":
        """设置追踪终点（找到此函数时停止）。"""
        self._target = target_function
        return self

    def run(self) -> "TraceResult":
        """执行追踪，返回结果对象。"""
        if not self._entry:
            raise ValueError("请先调用 from_entry() 设置入口函数")

        self._ensure_loaded()

        path_nodes = self._trace(
            entry=self._entry,
            conditions=self._conditions,
            target=self._target,
        )

        return TraceResult(
            entry=self._entry,
            target=self._target,
            conditions=dict(self._conditions),
            nodes=path_nodes,
            anchors=self._anchors,
        )

    # ── 独立调用接口（不用链式）──────────────────────────────

    def trace_path(
        self,
        entry: str,
        target: Optional[str] = None,
        conditions: Optional[dict] = None,
    ) -> "TraceResult":
        """直接调用版本，适合编程式使用。"""
        return (
            self.from_entry(entry)
            .until(target or "")
            ._run_with(conditions or {})
        )

    def get_pipeline(self, entry: str) -> list[PipelineNode]:
        """
        获取从入口出发的完整管线节点列表（不剪枝）。
        用于可视化。
        """
        self._ensure_loaded()
        nodes = []
        visited = set()
        queue = deque([(entry, 0)])

        while queue:
            name, depth = queue.popleft()
            if name in visited or depth > self.max_depth:
                continue
            visited.add(name)

            anchor = self._find_anchor(name)
            node = self._make_node(name, anchor, depth)
            nodes.append(node)

            for callee in self._call_graph.get(name, []):
                if callee not in visited:
                    queue.append((callee, depth + 1))

        return nodes

    # ── 核心追踪算法 ─────────────────────────────────────────

    def _trace(
        self,
        entry: str,
        conditions: dict,
        target: Optional[str],
        _depth: int = 0,
        _visited: Optional[set] = None,
    ) -> list[PipelineNode]:
        """
        深度优先追踪调用链。

        关键设计：
          - 遇到 for/while 循环：只追踪循环体一次（语义分析，不展开）
          - 遇到分叉（if/else）：用 conditions 剪枝选一条分支
          - 遇到 target：追踪到此节点后停止
        """
        if _visited is None:
            _visited = set()

        if entry in _visited or _depth > self.max_depth:
            return []

        _visited.add(entry)
        anchor = self._find_anchor(entry)
        node = self._make_node(entry, anchor, _depth)
        result = [node]

        # 找到目标，停止
        if target and entry == target:
            node.is_target = True
            return result

        callees = self._get_callees_with_conditions(entry, conditions, anchor)

        for callee in callees:
            sub = self._trace(callee, conditions, target, _depth + 1, _visited)
            result.extend(sub)
            # 如果子链已到达 target，不需要继续
            if target and any(n.is_target for n in sub):
                break

        return result

    def _get_callees_with_conditions(
        self, func_name: str, conditions: dict, anchor: Optional[dict]
    ) -> list[str]:
        """
        获取调用列表，应用条件剪枝。

        简化版：从 call_graph 获取所有被调用函数，
        用 conditions 过滤掉不可能走到的分支。
        """
        all_callees = self._call_graph.get(func_name, [])
        if not conditions or not all_callees:
            return all_callees

        # 剪枝：如果锚点记录了分支条件信息，做精确过滤
        # 当前版本做保守处理：conditions 只排除明确标记 condition_false 的分支
        if anchor:
            branches = anchor.get("metadata", {}).get("branches", [])
            filtered = []
            for callee in all_callees:
                # 检查这个 callee 是否有分支条件限制
                branch_info = next((b for b in branches if b.get("callee") == callee), None)
                if branch_info:
                    cond_var = branch_info.get("condition_var")
                    cond_val = branch_info.get("condition_value")
                    if cond_var and cond_var in conditions:
                        # 条件不符合，剪掉这条分支
                        if conditions[cond_var] != cond_val:
                            continue
                filtered.append(callee)
            return filtered

        return all_callees

    def _make_node(self, name: str, anchor: Optional[dict], depth: int) -> PipelineNode:
        """从锚点数据构造管线节点。"""
        if not anchor:
            return PipelineNode(
                name=name,
                file="?",
                line_start=0,
                line_end=0,
                inputs=[],
                outputs=[],
                depth=depth,
            )

        meta = anchor.get("metadata", {})
        return PipelineNode(
            name=name,
            file=anchor.get("file", "?"),
            line_start=anchor.get("line_start", 0),
            line_end=anchor.get("line_end", 0),
            inputs=meta.get("parameters", []),
            outputs=meta.get("return_type", []) if isinstance(
                meta.get("return_type"), list
            ) else ([meta["return_type"]] if meta.get("return_type") else []),
            depth=depth,
            description=anchor.get("description", ""),
            hash=anchor.get("hash", ""),
        )

    def _run_with(self, conditions: dict) -> "TraceResult":
        """内部用：带条件执行追踪。"""
        self._conditions = conditions
        return self.run()

    # ── 数据加载 ─────────────────────────────────────────────

    def _ensure_loaded(self):
        if self._loaded:
            return
        try:
            from index.api.anchors import load_anchors
            raw = load_anchors(str(self.root))
            # 转换为 tracer 内部期望的格式
            self._anchors = {}
            for k, a in raw.items():
                callee_names = [
                    c.get("target", c) if isinstance(c, dict) else c
                    for c in a.callees
                ]
                self._anchors[k] = {
                    "name": a.symbol,
                    "file": a.file,
                    "line_start": a.line_start,
                    "line_end": a.line_end,
                    "hash": a.hash,
                    "description": a.description,
                    "metadata": {
                        "calls": callee_names,
                        "parameters": [v.get("name", "") for v in a.inputs],
                        "return_type": [v.get("name", "") for v in a.outputs],
                        "branches": [],
                    },
                }
            # 构建调用图：symbol → [callee_name, ...]
            self._call_graph = {}
            for a in raw.values():
                callee_names = [
                    c.get("target", c) if isinstance(c, dict) else c
                    for c in a.callees
                ]
                self._call_graph[a.symbol] = callee_names
        except FileNotFoundError:
            self._anchors = {}
            self._call_graph = {}
        self._loaded = True

    def _find_anchor(self, name: str) -> Optional[dict]:
        for k, v in self._anchors.items():
            if v.get("name") == name:
                return v
        for k, v in self._anchors.items():
            if k.endswith(f".{name}"):
                return v
        return None
