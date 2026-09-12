"""
deep_analyzer.py - 深度 AST 数据流分析器
========================================
使用 Python AST 模块深度分析代码：
  - 精确的函数签名提取
  - 完整的调用关系图
  - 变量级数据流追踪
  - 自动生成管线流程图
"""

import ast
import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict

@dataclass
class DataFlowEdge:
    """数据流边：从一个函数的输出到另一个函数的输入"""
    from_func: str             # 源函数 ID
    to_func: str               # 目标函数 ID
    var_name: str              # 传递的变量名
    var_type: str              # 变量类型
    transform: str = ""        # 变换操作（可选）

@dataclass
class DataFlowPath:
    """一条完整的数据流路径"""
    entry_point: str           # 入口函数 ID
    steps: List[str]           # 函数 ID 序列 [func_a, func_b, ...]
    edges: List[DataFlowEdge]  # 边（数据传递）

@dataclass
class FuncInfo:
    """函数信息"""
    id: str                    # 唯一 ID: module.func 或 module.Class.method
    name: str                  # 函数名
    qualified: str             # 限定名：Class.method
    file: str                  # 文件路径
    line_start: int            # 起始行
    line_end: int              # 结束行
    
    # 签名信息
    signature: str             # 完整签名文本
    args: List[Dict]           # [{name, type, default}]
    returns: str               # 返回类型
    
    # 调用关系
    calls: List[str]           # 调用的其他函数 ID
    called_by: List[str]       # 被谁调用（后填充）
    
    # 是否是入口点
    is_entry_point: bool = False
