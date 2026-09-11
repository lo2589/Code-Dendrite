"""
resolver.py - 继承链解析器 (Hard L3-003, L3-004, L3-008, L3-009)
==================================================================
核心继承链追踪逻辑。

对应TS: inheritanceResolver.ts
"""

from pathlib import PurePosixPath
from typing import List, Optional, Union, Set, Dict, Any

from base.inheritance.types import (
    ClassIndex, ClassEntry, ExternalClassEntry,
    ImportInfo, Location, MethodInfo
)
from relate.inheritance.external_lib import resolve_external_class, get_builtin_class_info

from relate.inheritance.resolver.resolve_base_class import resolve_base_class

def find_subclasses(index: ClassIndex, class_name: str) -> List[ClassEntry]:
    """
    查找类的所有子类（包括多层继承的子类）

    参数：
        index: 类索引
        class_name: 类名

    返回：
        子类列表
    """
    subclasses = []
    class_short_name = class_name.split('.')[-1].split('[')[0]
    visited = set()

    def search(name: str):
        for cls_name, cls in index.classes.items():
            if id(cls) in visited:
                continue

            for base in cls.bases:
                base_name = base.split('.')[-1].split('[')[0]
                if base_name == class_short_name or base == name:
                    visited.add(id(cls))
                    subclasses.append(cls)
                    search(cls_name)

    search(class_name)
    return subclasses

def resolve_all_bases(
    class_name: str,
    index: ClassIndex,
    max_depth: int = 10
) -> List[Union[ClassEntry, ExternalClassEntry]]:
    """
    解析类的所有基类（支持多继承）
    
    与 resolve_inheritance 不同，这个函数会追踪所有基类，
    而不仅仅是第一个基类的主继承链。
    
    参数:
        class_name: 类名
        index: 类索引
        max_depth: 最大深度
    
    返回:
        所有基类列表
    """
    all_bases = []
    visited = set()
    
    def _resolve_all(class_name: str, depth: int):
        if depth >= max_depth or class_name in visited:
            return
        
        visited.add(class_name)
        
        if class_name in index.classes:
            entry = index.classes[class_name]
            
            for base in entry.bases:
                # 处理泛型
                base_name = base
                if '[' in base:
                    base_name = base.split('[')[0]
                
                resolved = resolve_base_class(base_name, entry.file, entry.imports, index)
                
                if resolved:
                    if resolved.name not in visited:
                        if isinstance(resolved, ExternalClassEntry):
                            all_bases.append(resolved)
                        else:
                            all_bases.append(resolved)
                            _resolve_all(resolved.name, depth + 1)
                else:
                    builtin = get_builtin_class_info(base_name)
                    if builtin and builtin.name not in visited:
                        all_bases.append(builtin)
    
    _resolve_all(class_name, 0)
    return all_bases

def get_all_bases(
    index: ClassIndex,
    class_name: str
) -> List[str]:
    """
    获取类的所有基类（多继承）
    
    这是 resolve_all_bases 的简化版本，只返回基类名称列表。
    
    参数：
        index: 类索引
        class_name: 类名
    
    返回：
        所有基类名称列表
    """
    all_bases_entries = resolve_all_bases(class_name, index)
    return [entry.name for entry in all_bases_entries if entry.name != class_name]

def resolve_base_class_safe(
    base_name: str,
    index: ClassIndex,
    default_file: Optional[str] = None
) -> Optional[Union[ClassEntry, ExternalClassEntry]]:
    """
    安全版本的 resolve_base_class（不需要 imports）
    
    当没有 imports 信息时使用此函数。
    
    参数:
        base_name: 基类名
        index: 类索引
        default_file: 默认文件路径（可选）
    
    返回:
        ClassEntry 或 ExternalClassEntry
    """
    # 处理泛型
    if '[' in base_name:
        base_name = base_name.split('[')[0]
    
    # 处理模块前缀
    if '.' in base_name:
        parts = base_name.split('.')
        module_path = '.'.join(parts[:-1])
        class_name = parts[-1]
        
        external = resolve_external_class(class_name, module_path)
        if external:
            return external
        
        if class_name in index.classes:
            return index.classes[class_name]
        
        return None
    
    # 1. 检查索引
    if base_name in index.classes:
        return index.classes[base_name]
    
    # 2. 检查内置类
    builtin = get_builtin_class_info(base_name)
    if builtin:
        return builtin
    
    # 3. 尝试作为外部库解析
    common_modules = ['torch', 'torch.nn', 'numpy', 'tensorflow', 'keras']
    for module in common_modules:
        external = resolve_external_class(base_name, module)
        if external:
            return external
    
    return None
