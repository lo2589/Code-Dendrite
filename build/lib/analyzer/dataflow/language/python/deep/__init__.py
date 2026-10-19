"""
dataflow_analyzer.py - 深度数据流分析器
========================================
分析函数间的详细数据流：
  - 每个函数的输入参数 (a, b, v)
  - 每个函数的返回值 (c, d)
  - 返回值如何变换后传递给下一个函数
  - 完整的变量级调用链

输出格式:
{
  "flows": [
    {
      "entry": "function_A",
      "steps": [
        {
          "func": "A",
          "inputs": [{"name": "a", "type": "str", "source": "user_input"}, ...],
          "outputs": [{"name": "c", "type": "User"}, {"name": "d", "type": "str"}],
          "transformations": [
            {"from": "c", "to": "B.user", "transform": "User.validate()"},
            {"from": "d", "to": "E.token", "transform": "base64.encode()"}
          ]
        },
        {
          "func": "B",
          "inputs": [...],
          "outputs": [...],
          ...
        }
      ]
    }
  ]
}
"""

import ast
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from analyzer.dataflow.language.python.deep.data_flow_step import DataFlowStep
from analyzer.dataflow.language.python.deep.variable_info_etc import VariableInfo, FunctionDataFlow, DataFlowAnalyzer
from analyzer.dataflow.language.python.deep.main import main

__all__ = ['DataFlowStep', 'VariableInfo', 'FunctionDataFlow', 'DataFlowAnalyzer', 'main']
