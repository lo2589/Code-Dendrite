"""
node.py — 管线节点数据结构

每个函数对应一个 PipelineNode：
  输入插槽（inputs）← 函数参数类型
  输出插槽（outputs）← 返回值类型
  节点内部           ← 函数体逻辑

节点是替换和兼容性检查的基本单位。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PipelineNode:
    """
    管线中的一个节点（对应一个函数）。

    属性：
        name:        函数名
        file:        所在文件
        line_start:  起始行
        line_end:    结束行
        inputs:      输入插槽（参数名列表）
        outputs:     输出插槽（返回类型列表）
        depth:       在调用链中的深度（0 = 入口）
        description: 锚点描述
        hash:        结构哈希
        is_target:   是否是追踪目标节点
        is_breakpoint: 是否设置了断点
        conditions:  到达此节点时的已知条件
        alternatives: 可替换的候选节点名列表
    """
    name: str
    file: str
    line_start: int
    line_end: int
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    depth: int = 0
    description: str = ""
    hash: str = ""
    is_target: bool = False
    is_breakpoint: bool = False
    conditions: dict = field(default_factory=dict)
    alternatives: list[str] = field(default_factory=list)

    @property
    def location(self) -> str:
        return f"{self.file}:L{self.line_start}–L{self.line_end}"

    @property
    def signature(self) -> str:
        params = ", ".join(self.inputs)
        ret = " → " + ", ".join(self.outputs) if self.outputs else ""
        return f"{self.name}({params}){ret}"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "file": self.file,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "depth": self.depth,
            "description": self.description,
            "hash": self.hash,
            "is_target": self.is_target,
            "is_breakpoint": self.is_breakpoint,
            "conditions": self.conditions,
            "alternatives": self.alternatives,
            "signature": self.signature,
            "location": self.location,
        }

    def __repr__(self) -> str:
        indent = "  " * self.depth
        marker = " ◆" if self.is_target else (" ● " if self.is_breakpoint else "")
        return f"{indent}[{self.depth}] {self.signature}  {self.location}{marker}"
