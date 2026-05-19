"""
types.py - L4_DataFlow 数据类型定义
====================================
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class VariableInfo:
    """变量信息"""
    name: str
    var_type: str                      # 推断类型
    source: str                        # "parameter" | "return" | "literal" | "call_result"
    line: int
    transformed_by: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.var_type,
            "source": self.source,
            "line": self.line,
            "transformed_by": self.transformed_by
        }


@dataclass
class Transformation:
    """变量变换"""
    from_var: str                      # 源变量
    to_var: str                        # 目标变量
    operation: str                     # 变换操作（如 "User.validate()"）
    line: int
    code_snippet: str = ""             # 代码片段
    
    def to_dict(self) -> dict:
        return {
            "from_var": self.from_var,
            "to_var": self.to_var,
            "operation": self.operation,
            "line": self.line,
            "code_snippet": self.code_snippet
        }


@dataclass
class FunctionCall:
    """函数调用"""
    target: str                        # 被调用函数
    args: List[str]                    # 参数列表
    line: int
    code_snippet: str
    return_var: Optional[str] = None   # 返回值赋给的变量
    
    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "args": self.args,
            "line": self.line,
            "code_snippet": self.code_snippet,
            "return_var": self.return_var
        }


@dataclass
class FunctionDataFlow:
    """函数数据流"""
    func_id: str
    file: str
    line_start: int
    line_end: int
    inputs: List[VariableInfo] = field(default_factory=list)
    outputs: List[VariableInfo] = field(default_factory=list)
    transformations: List[Transformation] = field(default_factory=list)
    calls: List[FunctionCall] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "func_id": self.func_id,
            "file": self.file,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "inputs": [i.to_dict() for i in self.inputs],
            "outputs": [o.to_dict() for o in self.outputs],
            "transformations": [t.to_dict() for t in self.transformations],
            "calls": [c.to_dict() for c in self.calls]
        }


@dataclass
class VariableTrace:
    """变量追踪结果"""
    variable_name: str
    origin: VariableInfo               # 变量来源
    transformations: List[Transformation]  # 经历的变换
    final_usage: List[str]             # 最终使用位置
    passed_to: List[str]               # 传递给了哪些函数
    
    def to_dict(self) -> dict:
        return {
            "variable_name": self.variable_name,
            "origin": self.origin.to_dict(),
            "transformations": [t.to_dict() for t in self.transformations],
            "final_usage": self.final_usage,
            "passed_to": self.passed_to
        }


@dataclass
class CallChainStep:
    """调用链步骤"""
    step_index: int
    function: str
    file: str
    line: int
    inputs: List[Dict]                 # [{name, type, source}]
    outputs: List[Dict]                # [{name, type}]
    transformations: List[Dict]
    next_function: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "step": self.step_index,
            "function": self.function,
            "file": self.file,
            "line": self.line,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "transformations": self.transformations,
            "next": self.next_function
        }


@dataclass
class CallChain:
    """调用链"""
    entry_point: str
    depth: int
    steps: List[CallChainStep] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "entry": self.entry_point,
            "depth": self.depth,
            "steps": [s.to_dict() for s in self.steps]
        }
