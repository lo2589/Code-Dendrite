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

from synth.codeTree.deep_analyzer.data_flow import DataFlowEdge, DataFlowPath, FuncInfo
from synth.codeTree.deep_analyzer.core import DeepAnalyzer
from synth.codeTree.deep_analyzer.generate_pipeline_html import generate_pipeline_html, main

__all__ = ['DataFlowEdge', 'DataFlowPath', 'FuncInfo', 'DeepAnalyzer', 'generate_pipeline_html', 'main']
