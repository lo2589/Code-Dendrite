"""
ast_parser.py - Python AST解析器 (Easy L3-002)
================================================
解析Python文件，提取类和导入信息。

对应TS: pythonAST.ts
"""

import ast
from pathlib import Path
from typing import List, Optional

from scanner.shared.inheritance_types import ClassInfo, MethodInfo, ImportInfo, PythonFileInfo

def parse_generic_bases(bases_text: str) -> List[str]:
    """
    解析泛型基类
    
    例如: Dict[str, Any] -> ['Dict']
    
    参数:
        bases_text: 基类文本
    
    返回:
        解析后的基类列表
    """
    import typing
    
    result = []
    
    try:
        origin = typing.get_origin(bases_text)
        if origin:
            result.append(origin.__name__ if hasattr(origin, '__name__') else str(origin))
        
        args = typing.get_args(bases_text)
        for arg in args:
            if hasattr(arg, '__name__'):
                result.append(arg.__name__)
            elif hasattr(arg, '__origin__'):
                result.append(str(arg.__origin__))
    except:
        pass
    
    if not result:
        if '[' in bases_text:
            result.append(bases_text.split('[')[0])
        else:
            result.append(bases_text)
    
    return result
