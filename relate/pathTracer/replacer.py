"""
replacer.py — 节点替换器

管线节点替换的核心逻辑：
  1. 类型兼容性检查（输入/输出插槽是否匹配）
  2. 语义差异报告（行为上有什么不同）
  3. 生成新管线（替换后的结果）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from relate.pathTracer.result import TraceResult
from relate.pathTracer.node import PipelineNode


@dataclass
class ReplaceProposal:
    """
    节点替换方案。

    属性：
        original:      原始节点名
        replacement:   替换节点名
        compatible:    是否类型兼容（可以物理连接）
        input_match:   输入插槽匹配情况
        output_match:  输出插槽匹配情况
        semantic_diff: 语义差异列表（行为不同点）
        risk_level:    风险等级 low/medium/high
        new_pipeline:  替换后的管线 JSON
    """
    original: str
    replacement: str
    compatible: bool = False
    input_match: bool = False
    output_match: bool = False
    semantic_diff: list[str] = field(default_factory=list)
    risk_level: str = "unknown"
    new_pipeline: Optional[str] = None

    def __str__(self) -> str:
        lines = [
            f"替换方案: {self.original} → {self.replacement}",
            f"  类型兼容: {'✓' if self.compatible else '✗'}",
            f"  输入匹配: {'✓' if self.input_match else '✗'}",
            f"  输出匹配: {'✓' if self.output_match else '✗'}",
            f"  风险等级: {self.risk_level}",
        ]
        if self.semantic_diff:
            lines.append("  语义差异:")
            for d in self.semantic_diff:
                lines.append(f"    - {d}")
        return "\n".join(lines)


class NodeReplacer:
    """节点替换器。"""

    def __init__(self, anchors: dict):
        self._anchors = anchors

    def propose(
        self,
        trace_result: "TraceResult",
        original: str,
        replacement: str,
        check_compat: bool = True,
    ) -> ReplaceProposal:
        """生成替换方案。"""
        orig_node = trace_result.find_node(original)
        repl_anchor = self._find_anchor(replacement)

        if not orig_node:
            return ReplaceProposal(
                original=original,
                replacement=replacement,
                semantic_diff=[f"原始节点 '{original}' 不在当前追踪路径中"],
                risk_level="high",
            )

        if not repl_anchor:
            return ReplaceProposal(
                original=original,
                replacement=replacement,
                semantic_diff=[f"替换节点 '{replacement}' 在锚点库中未找到"],
                risk_level="high",
            )

        # 构建替换节点
        repl_meta = repl_anchor.get("metadata", {})
        repl_inputs = repl_meta.get("parameters", [])
        repl_outputs_raw = repl_meta.get("return_type", [])
        repl_outputs = repl_outputs_raw if isinstance(repl_outputs_raw, list) else (
            [repl_outputs_raw] if repl_outputs_raw else []
        )

        # 检查输入兼容
        input_match = self._check_inputs(orig_node.inputs, repl_inputs)
        output_match = self._check_outputs(orig_node.outputs, repl_outputs)
        compatible = input_match and output_match

        # 语义差异分析
        semantic_diff = self._analyze_semantic_diff(orig_node, repl_anchor)

        # 风险等级
        risk = self._assess_risk(compatible, semantic_diff)

        # 生成新管线（若兼容）
        new_pipeline = None
        if compatible:
            new_pipeline = self._build_new_pipeline(
                trace_result, original, replacement, repl_anchor, repl_inputs, repl_outputs
            )

        return ReplaceProposal(
            original=original,
            replacement=replacement,
            compatible=compatible,
            input_match=input_match,
            output_match=output_match,
            semantic_diff=semantic_diff,
            risk_level=risk,
            new_pipeline=new_pipeline,
        )

    def _check_inputs(self, orig: list[str], repl: list[str]) -> bool:
        """简化版：参数数量相同视为兼容（未来可扩展类型检查）。"""
        if not orig and not repl:
            return True
        return len(orig) == len(repl)

    def _check_outputs(self, orig: list[str], repl: list[str]) -> bool:
        """输出类型兼容检查（简化版）。"""
        if not orig and not repl:
            return True
        if not orig or not repl:
            return True  # 有一方无类型信息，保守认为兼容
        return len(orig) == len(repl)

    def _analyze_semantic_diff(
        self, orig_node: PipelineNode, repl_anchor: dict
    ) -> list[str]:
        """
        分析语义差异：从 anchor 的 description 和 metadata 提取不同点。
        """
        diffs = []
        orig_desc = orig_node.description.lower()
        repl_desc = repl_anchor.get("description", "").lower()

        # 简单关键词差异检测
        security_keywords = ["auth", "validate", "verify", "check", "permission", "ip"]
        perf_keywords = ["cache", "fast", "lite", "quick", "skip"]

        orig_has_security = any(k in orig_desc for k in security_keywords)
        repl_has_security = any(k in repl_desc for k in security_keywords)

        if orig_has_security and not repl_has_security:
            diffs.append("替换版本可能缺少安全校验逻辑")

        orig_has_perf = any(k in orig_desc for k in perf_keywords)
        repl_has_perf = any(k in repl_desc for k in perf_keywords)

        if repl_has_perf and not orig_has_perf:
            diffs.append("替换版本是精简/快速版，可能跳过了某些检查")

        # 如果 anchor 记录了行为差异
        repl_meta = repl_anchor.get("metadata", {})
        behavior_notes = repl_meta.get("behavior_notes", [])
        diffs.extend(behavior_notes)

        return diffs

    def _assess_risk(self, compatible: bool, semantic_diff: list[str]) -> str:
        if not compatible:
            return "high"
        if any("安全" in d or "auth" in d.lower() for d in semantic_diff):
            return "high"
        if semantic_diff:
            return "medium"
        return "low"

    def _build_new_pipeline(
        self,
        trace_result: "TraceResult",
        original: str,
        replacement: str,
        repl_anchor: dict,
        repl_inputs: list,
        repl_outputs: list,
    ) -> str:
        """构建替换后的管线 JSON。"""
        import json
        new_nodes = []
        for node in trace_result.nodes:
            if node.name == original:
                new_node = PipelineNode(
                    name=replacement,
                    file=repl_anchor.get("file", "?"),
                    line_start=repl_anchor.get("line_start", 0),
                    line_end=repl_anchor.get("line_end", 0),
                    inputs=repl_inputs,
                    outputs=repl_outputs,
                    depth=node.depth,
                    description=repl_anchor.get("description", ""),
                    hash=repl_anchor.get("hash", ""),
                )
                new_nodes.append(new_node)
            else:
                new_nodes.append(node)

        name_seq = [n.name for n in new_nodes]
        edges = [{"from": name_seq[i], "to": name_seq[i + 1]}
                 for i in range(len(name_seq) - 1)]

        return json.dumps({
            "replaced": {original: replacement},
            "nodes": [n.to_dict() for n in new_nodes],
            "edges": edges,
        }, ensure_ascii=False, indent=2)

    def _find_anchor(self, name: str) -> Optional[dict]:
        for k, v in self._anchors.items():
            if v.get("name") == name or k.endswith(f".{name}"):
                return v
        return None
