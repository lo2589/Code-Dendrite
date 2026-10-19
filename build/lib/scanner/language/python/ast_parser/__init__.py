"""
ast_parser.py - Python AST解析器 (Easy L3-002)
================================================
解析Python文件，提取类和导入信息。

对应TS: pythonAST.ts
"""

import ast
from pathlib import Path
from typing import List, Optional

from analyzer.shared.legacy.inheritance.types import ClassInfo, MethodInfo, ImportInfo, PythonFileInfo

from scanner.language.python.ast_parser.parse import _check_has_super, _parse_method, _parse_class, _parse_type_annotation, extract_parameter_types, extract_return_type, get_decorators, parse_python_file, parse_symbol, get_method_info, has_abstract_decorator, has_override_decorator
from scanner.language.python.ast_parser.parse_generic_bases import parse_generic_bases

__all__ = ['_check_has_super', '_parse_method', '_parse_class', '_parse_type_annotation', 'extract_parameter_types', 'extract_return_type', 'get_decorators', 'parse_python_file', 'parse_symbol', 'get_method_info', 'has_abstract_decorator', 'has_override_decorator', 'parse_generic_bases']
