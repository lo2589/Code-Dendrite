"""
external_lib.py - 外部库解析 (Medium L3-005, Hard L3-006, Easy L3-007)
========================================================================
解析外部库和内置类。

对应TS: externalLibResolver.ts
"""

from pathlib import Path
from typing import List, Optional, Dict
import sys

from base.inheritance.types import ExternalClassEntry, MethodInfo
from parse.inheritance.ast_parser import parse_python_file


# 缓存
_site_packages_cache: List[str] = []
_external_class_cache: Dict[str, ExternalClassEntry] = {}

from relate.inheritance.external_lib.get_builtin_class_info import get_builtin_class_info, resolve_module_path

def resolve_external_class(class_name: str, module_path: str) -> Optional[ExternalClassEntry]:
    """
    解析外部库类 (Hard L3-006)
    
    参数:
        class_name: 类名
        module_path: 模块路径
    
    返回:
        ExternalClassEntry对象，未找到返回None
    
    对应TS: externalLibResolver.ts 的 resolveExternalClass()
    """
    cache_key = f"{module_path}.{class_name}"
    if cache_key in _external_class_cache:
        return _external_class_cache[cache_key]
    
    # 首先检查内置类
    builtin = get_builtin_class_info(class_name)
    if builtin:
        return builtin
    
    # 解析模块文件
    file_path = resolve_module_path(module_path)
    if not file_path:
        # 尝试更短的模块路径
        parts = module_path.split(".")
        for i in range(len(parts), 0, -1):
            shorter_path = ".".join(parts[:i])
            file_path = resolve_module_path(shorter_path)
            if file_path:
                break
    
    if not file_path:
        return None
    
    try:
        file_info = parse_python_file(file_path)
        for cls in file_info.classes:
            if cls.name == class_name:
                entry = ExternalClassEntry(
                    name=class_name,
                    file=file_path,
                    line=cls.line,
                    bases=cls.bases,
                    module=module_path,
                    methods=cls.methods
                )
                _external_class_cache[cache_key] = entry
                return entry
    except Exception:
        pass
    
    # 未在文件中找到类，可能是动态导入或C扩展
    # 创建一个占位条目
    entry = ExternalClassEntry(
        name=class_name,
        file=file_path or f"[{module_path}]",
        line=0,
        bases=[],
        module=module_path
    )
    _external_class_cache[cache_key] = entry
    return entry
