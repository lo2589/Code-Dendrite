"""
codeGenome/python_extractor.py - Python 代码提取器
=================================================
提取 Python 文件中的所有锚点，包括：
- import 语句
- 顶层赋值
- __main__ 块内的裸语句
- 类定义
- 方法定义
- 函数定义

锚点命名规范:
    relative/path.py::symbol
    relative/path.py::category:name
"""

import ast
import hashlib
import os

try:
    # CPython 内部行切分（与 node.lineno 对齐）；用来按文件缓存切分，避免每个节点重切整文件
    from ast import _splitlines_no_ff as _ast_splitlines
except Exception:
    _ast_splitlines = None
from pathlib import Path
from typing import List, Optional, Dict, Set

from analyzer.shared.legacy.codeGenome.types import (
    CodeAnchor, AnchorIndex, AnchorCategory,
    ImportInfo, ClassInfo, FunctionInfo, TopLevelBlock
)
from scanner.project.config_detector import ConfigDetector
from analyzer.shared.legacy.codeGenome.identity import asset_anchor_id, canonical_file_id, symbol_anchor_id
from analyzer.shared.codedendrite_ignore import CodeDendriteIgnore
import re as _re

from scanner.language.python.genome.core import PythonExtractor

def extract_python_directory(dir_path: str) -> AnchorIndex:
    """提取 Python 目录的锚点（便捷函数）"""
    extractor = PythonExtractor()
    return extractor.extract_directory(dir_path)

def extract_python_file(file_path: str) -> AnchorIndex:
    """提取 Python 文件的锚点（便捷函数）"""
    extractor = PythonExtractor()
    return extractor.extract_file(file_path)
