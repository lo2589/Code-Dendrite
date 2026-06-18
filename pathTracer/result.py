"""
result.py — 追踪结果对象

TraceResult 包含一次路径追踪的完整结果：
  - 节点列表（管线）
  - 可视化输出
  - 节点替换入口
  - Debug 断点设置
"""
from __future__ import annotations

import json
from typing import Optional
from .node import PipelineNode


class TraceResult:
    """
    一次 PathTracer.run() 的结果。

    用法：
        result = tracer.from_entry("main").until("db.save").run()

        print(result)               # 文字管线图
        result.to_pipeline()        # JSON（接可视化）
        result.set_breakpoint("validate_user")
        result.replace_node("validate_user", "validate_user_lite")
    """

    def __init__(
        self,
        entry: str,
        target: Optional[str],
        conditions: dict,
        nodes: list[PipelineNode],
        anchors: dict,
    ):
        self.entry = entry
        self.target = target
        self.conditions = conditions
        self.nodes = nodes
        self._anchors = anchors

    # ── 展示 ─────────────────────────────────────────────────

    def __str__(self) -> str:
        lines = [
            f"PathTrace: {self.entry}",
            f"  target : {self.target or '(全链路)'}",
            f"  given  : {self.conditions}",
            f"  nodes  : {len(self.nodes)} 个",
            "",
        ]
        for node in self.nodes:
            lines.append(repr(node))
        return "\n".join(lines)

    def to_pipeline(self) -> str:
        """
        返回 JSON 格式的管线结构，可接 ComfyUI 风格可视化。

        格式：
        {
          "entry": "handle_request",
          "target": "db.save",
          "conditions": {...},
          "nodes": [...],
          "edges": [{"from": "A", "to": "B"}]
        }
        """
        nodes_data = [n.to_dict() for n in self.nodes]

        # 构建边（相邻节点间）
        edges = []
        name_seq = [n.name for n in self.nodes]
        for i in range(len(name_seq) - 1):
            edges.append({"from": name_seq[i], "to": name_seq[i + 1]})

        pipeline = {
            "entry": self.entry,
            "target": self.target,
            "conditions": self.conditions,
            "nodes": nodes_data,
            "edges": edges,
        }
        return json.dumps(pipeline, ensure_ascii=False, indent=2)

    def to_mermaid(self) -> str:
        """
        生成 Mermaid 流程图格式（可嵌入 Markdown）。
        """
        lines = ["```mermaid", "flowchart TD"]
        for node in self.nodes:
            label = node.signature.replace('"', "'")
            shape = f'["{label}"]'
            if node.is_target:
                shape = f'(["{label}"])'
            elif node.is_breakpoint:
                shape = f'{{"{label}"}}'
            lines.append(f"  {node.name}{shape}")

        for i in range(len(self.nodes) - 1):
            a = self.nodes[i].name
            b = self.nodes[i + 1].name
            out = self.nodes[i].outputs[0] if self.nodes[i].outputs else ""
            arrow = f"-->|{out}|" if out else "-->"
            lines.append(f"  {a} {arrow} {b}")

        lines.append("```")
        return "\n".join(lines)

    # ── 断点 ─────────────────────────────────────────────────

    def set_breakpoint(self, node_name: str) -> "TraceResult":
        """在指定节点设置断点（标记，用于 Debug 流程）。"""
        for node in self.nodes:
            if node.name == node_name:
                node.is_breakpoint = True
                return self
        raise ValueError(f"节点 '{node_name}' 不在当前追踪路径中")

    def get_breakpoints(self) -> list["PipelineNode"]:
        """返回所有设置了断点的节点。"""
        return [n for n in self.nodes if n.is_breakpoint]

    # ── 节点替换 ─────────────────────────────────────────────

    def replace_node(
        self, original: str, replacement: str, check_compatibility: bool = True
    ) -> "ReplaceProposal":
        """
        提出节点替换方案。

        返回 ReplaceProposal，包含：
          - 兼容性检查结果
          - 语义差异报告
          - 确认后的新管线
        """
        from .replacer import NodeReplacer
        replacer = NodeReplacer(self._anchors)
        return replacer.propose(self, original, replacement, check_compatibility)

    # ── 查询 ─────────────────────────────────────────────────

    def find_node(self, name: str) -> Optional[PipelineNode]:
        """在追踪结果中查找节点。"""
        for node in self.nodes:
            if node.name == name:
                return node
        return None

    def get_path_names(self) -> list[str]:
        """返回路径上的函数名列表。"""
        return [n.name for n in self.nodes]

    def summary(self) -> str:
        """一行摘要。"""
        path = " → ".join(self.get_path_names())
        return f"{path}  （{len(self.nodes)} 个节点）"
