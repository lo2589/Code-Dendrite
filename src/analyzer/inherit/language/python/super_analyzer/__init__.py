"""
super_analyzer.py - Python super() 调用分析器
==============================================
从 TypeScript 迁移的 Python super() 调用分析工具。

功能：
- 分析类继承链中所有 super() 调用
- 追踪 super() 调用的参数和目标
- 验证 super() 调用的正确性

用法：
    from analyzer.inherit.language.python.super_analyzer import analyze_super_calls, find_super_in_method

    calls = analyze_super_calls(chain)
    method_calls = find_super_in_method(file_path, class_name, method_name)
"""

import ast
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
from pathlib import Path

from analyzer.inherit.language.python.super_analyzer.super_chain import SuperCallInfo, SuperAnalyzer, SuperChain, analyze_super_calls, build_super_chain, find_super_in_method
from analyzer.inherit.language.python.super_analyzer.validate_super_calls import validate_super_calls

__all__ = ['SuperCallInfo', 'SuperAnalyzer', 'SuperChain', 'analyze_super_calls', 'build_super_chain', 'find_super_in_method', 'validate_super_calls']
