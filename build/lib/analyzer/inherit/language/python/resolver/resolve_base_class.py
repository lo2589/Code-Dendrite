"""
resolver.py - 继承链解析器 (Hard L3-003, L3-004, L3-008, L3-009)
==================================================================
核心继承链追踪逻辑。

对应TS: inheritanceResolver.ts
"""

from pathlib import PurePosixPath
from typing import List, Optional, Union, Set, Dict, Any

from analyzer.shared.legacy.inheritance.types import (
    ClassIndex, ClassEntry, ExternalClassEntry,
    ImportInfo, Location, MethodInfo
)
from analyzer.inherit.language.python.external_lib import resolve_external_class, get_builtin_class_info

def compute_full_mro(class_name: str, index: ClassIndex) -> List[str]:
    """
    计算完整的MRO（处理多继承）
    
    使用C3线性化算法。
    """
    if class_name not in index.classes:
        # 可能是内置类
        builtin = get_builtin_class_info(class_name)
        if builtin:
            return [class_name] + builtin.bases
        return [class_name]
    
    entry = index.classes[class_name]
    
    if not entry.bases:
        return [class_name]
    
    # 获取所有基类的MRO
    base_mros = []
    for base in entry.bases:
        base_mro = compute_full_mro(base, index)
        if base_mro:
            base_mros.append(base_mro)
    
    # 添加基类列表本身
    base_mros.append(list(entry.bases))
    
    # C3 merge
    result = [class_name]
    result.extend(_c3_merge(base_mros))
    
    return result

def _c3_merge(lists: List[List[str]]) -> List[str]:
    """C3线性化merge算法"""
    result = []
    
    while True:
        # 移除空列表
        lists = [lst for lst in lists if lst]
        if not lists:
            break
        
        # 找一个好的候选
        for lst in lists:
            candidate = lst[0]
            # 检查candidate是否在其他列表的尾部
            is_good = True
            for other in lists:
                if candidate in other[1:]:
                    is_good = False
                    break
            
            if is_good:
                result.append(candidate)
                # 从所有列表中移除candidate
                for lst2 in lists:
                    if candidate in lst2:
                        lst2.remove(candidate)
                break
        else:
            # 无法找到好的候选，存在循环
            raise ValueError(f"Cannot create a consistent MRO for {lists}")
    
    return result

def _import_to_file_path(from_path: str, current_file: str) -> Optional[str]:
    """Convert an import from_path to a relative .py file path."""
    if not from_path:
        return None
    current = PurePosixPath(current_file.replace("\\", "/"))
    if from_path.startswith('.'):
        level = len(from_path) - len(from_path.lstrip('.'))
        module_part = from_path.lstrip('.')
        base = current.parent
        for _ in range(level - 1):
            base = base.parent
        if module_part:
            return str(base / module_part.replace('.', '/')) + '.py'
        return None
    else:
        return from_path.replace('.', '/') + '.py'

def resolve_base_class(
    base_name: str,
    current_file: str,
    imports: List[ImportInfo],
    index: ClassIndex
) -> Optional[Union[ClassEntry, ExternalClassEntry]]:
    """
    解析基类名到具体类 (Hard L3-004)
    
    参数:
        base_name: 基类名
        current_file: 当前文件路径
        imports: 导入信息列表
        index: 类索引
    
    返回:
        ClassEntry或ExternalClassEntry，未找到返回None
    
    对应TS: inheritanceResolver.ts 的 resolveBaseClass()
    
    查找顺序:
        1. 工作区索引（同名类）
        2. 内置类
        3. 从import语句解析
    """
    # 处理泛型
    if '[' in base_name:
        base_name = base_name.split('[')[0]
    
    # 处理模块前缀（如 abc.ABC）
    if '.' in base_name:
        parts = base_name.split('.')
        module_path = '.'.join(parts[:-1])
        class_name = parts[-1]
        
        # 尝试解析外部类
        external = resolve_external_class(class_name, module_path)
        if external:
            return external
        
        # 也检查索引
        if class_name in index.classes:
            return index.classes[class_name]
        
        return None
    
    # 1. 直接在索引中查找
    if base_name in index.classes:
        return index.classes[base_name]
    
    # 2. 检查内置类
    builtin = get_builtin_class_info(base_name)
    if builtin:
        return builtin
    
    # 3. 从import解析（import-first：优先用文件路径精确定位，绕过 name collision）
    for imp in imports:
        # from module import ClassName 或 from module import ClassName as Alias
        if imp.from_path:
            for original, alias in imp.aliases.items():
                if alias == base_name or original == base_name:
                    actual_name = original if original != '*' else base_name

                    # 优先：用 from_path 解析出文件路径，走 classes_fq 精确查找
                    file_path = _import_to_file_path(imp.from_path, current_file)
                    if file_path:
                        fq_key = "{}::{}".format(file_path, actual_name)
                        if fq_key in index.classes_fq:
                            return index.classes_fq[fq_key]
                        # 路径中 \ 与 / 混用时再试一次
                        fq_key2 = "{}::{}".format(file_path.replace("/", "\\"), actual_name)
                        if fq_key2 in index.classes_fq:
                            return index.classes_fq[fq_key2]

                    # 退而求其次：name-only（可能不准，但总比 None 好）
                    if actual_name in index.classes:
                        return index.classes[actual_name]

                    # 外部库
                    external = resolve_external_class(actual_name, imp.from_path)
                    if external:
                        return external

        # import module 或 import module as alias
        elif imp.module:
            for original, alias in imp.aliases.items():
                if base_name.startswith(alias + "."):
                    class_name = base_name[len(alias) + 1:]
                    external = resolve_external_class(class_name, imp.module)
                    if external:
                        return external

    return None
