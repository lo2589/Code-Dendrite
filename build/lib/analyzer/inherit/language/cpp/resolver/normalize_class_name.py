"""
resolver.py - C++ 继承链解析器
=================================
解析 C++ 类的继承链，支持：
- 多继承
- 模板类
- 命名空间
- 外部库

用法：
    from analyzer.inherit.language.cpp.resolver import resolve_inheritance, compute_mro

    chain = resolve_inheritance(index, "MyClass")
    mro = compute_mro(index, "MyClass")
"""

from typing import List, Optional, Set, Dict, Any
import re

from analyzer.shared.legacy.cpp_inheritance.types import CppClassIndex, CppClassInfo, CppInheritanceEntry, CppLocation

def _normalize_class_name(name: str) -> str:
    """标准化类名"""
    name = name.strip()

    name = re.sub(r'<[^>]+>', '', name)

    if '::' in name:
        return name.split('::')[-1]

    return name

def compute_full_mro(index: CppClassIndex, class_name: str) -> List[str]:
    """
    计算完整的 MRO（支持多继承）

    参数：
        index: 类索引
        class_name: 类名

    返回：
        完整 MRO 列表
    """
    cls = index.get(class_name)

    if not cls or not cls.bases:
        return [class_name]

    base_mros = []
    for base in cls.bases:
        base_name = _normalize_class_name(base)
        base_mro = compute_full_mro(index, base_name)
        if base_mro:
            base_mros.append(base_mro)

    base_mros.append(list(cls.bases))

    result = [class_name]
    result.extend(_c3_merge(base_mros))

    return result

def _c3_merge(lists: List[List[str]]) -> List[str]:
    """C3 线性化合并"""
    import re

    result = []

    while True:
        lists = [lst for lst in lists if lst]
        if not lists:
            break

        for lst in lists:
            candidate = lst[0]
            is_good = True

            for other in lists:
                if candidate in other[1:]:
                    is_good = False
                    break

            if is_good:
                result.append(candidate)
                for lst2 in lists:
                    if candidate in lst2:
                        lst2.remove(candidate)
                break
        else:
            break

    return result

def resolve_inheritance(
    index: CppClassIndex,
    class_name: str,
    max_depth: int = 20
) -> List[CppInheritanceEntry]:
    """
    解析类的继承链

    参数：
        index: 类索引
        class_name: 类名
        max_depth: 最大深度

    返回：
        继承链列表
    """
    chain: List[CppInheritanceEntry] = []
    visited: Set[str] = set()

    _resolve_recursive(index, class_name, chain, visited, 0, max_depth)

    return chain

def _resolve_recursive(
    index: CppClassIndex,
    class_name: str,
    chain: List[CppInheritanceEntry],
    visited: Set[str],
    depth: int,
    max_depth: int
):
    """递归解析继承链"""
    if depth >= max_depth:
        return

    if class_name in visited:
        return

    visited.add(class_name)

    cls = index.get(class_name)

    if cls:
        entry = CppInheritanceEntry(
            name=cls.name,
            file=cls.file,
            line=cls.line,
            bases=cls.bases,
            methods=cls.methods,
            depth=depth,
            is_external=cls.is_external
        )
        chain.append(entry)

        if not cls.bases:
            return

        for base in cls.bases:
            base_name = _normalize_class_name(base)
            if base_name not in visited:
                _resolve_recursive(index, base_name, chain, visited, depth + 1, max_depth)
    else:
        chain.append(CppInheritanceEntry(
            name=class_name,
            file="[forward_declaration]",
            line=0,
            bases=[],
            methods=[],
            depth=depth,
            is_external=True
        ))

def compute_mro(index: CppClassIndex, class_name: str) -> List[str]:
    """
    计算方法解析顺序（MRO）

    参数：
        index: 类索引
        class_name: 类名

    返回：
        MRO 列表
    """
    chain = resolve_inheritance(index, class_name)
    return [entry.name for entry in chain]

def find_method_origin(
    index: CppClassIndex,
    class_name: str,
    method_name: str
) -> Optional[CppLocation]:
    """
    查找方法定义位置

    参数：
        index: 类索引
        class_name: 类名
        method_name: 方法名

    返回：
        方法定义位置
    """
    chain = resolve_inheritance(index, class_name)

    for entry in chain:
        for method in entry.methods:
            if method.name == method_name:
                return CppLocation(
                    file=entry.file,
                    line=method.start_line
                )

    return None

def get_override_chain(
    index: CppClassIndex,
    class_name: str,
    method_name: str
) -> List[Dict[str, Any]]:
    """
    获取方法覆盖链

    参数：
        index: 类索引
        class_name: 类名
        method_name: 方法名

    返回：
        覆盖链列表
    """
    chain = resolve_inheritance(index, class_name)
    overrides = []

    for entry in chain:
        for method in entry.methods:
            if method.name == method_name:
                overrides.append({
                    "class": entry.name,
                    "file": entry.file,
                    "line": method.start_line,
                    "is_override": method.is_override,
                    "is_virtual": method.is_virtual,
                    "is_pure_virtual": method.is_pure_virtual
                })

    return overrides

def get_virtual_methods(
    index: CppClassIndex,
    class_name: str
) -> List[Dict[str, Any]]:
    """
    获取类的虚方法列表

    参数：
        index: 类索引
        class_name: 类名

    返回：
        虚方法列表
    """
    chain = resolve_inheritance(index, class_name)
    virtual_methods = []

    for entry in chain:
        for method in entry.methods:
            if method.is_virtual or method.is_override:
                virtual_methods.append({
                    "class": entry.name,
                    "name": method.name,
                    "line": method.start_line,
                    "is_override": method.is_override,
                    "is_pure_virtual": method.is_pure_virtual
                })

    return virtual_methods

def is_subclass_of(
    index: CppClassIndex,
    class_name: str,
    base_name: str
) -> bool:
    """
    检查是否是某类的子类

    参数：
        index: 类索引
        class_name: 类名
        base_name: 基类名

    返回：
        如果是子类返回 True
    """
    mro = compute_mro(index, class_name)
    base_short = _normalize_class_name(base_name)

    for name in mro:
        if _normalize_class_name(name) == base_short:
            return True

    return False

def find_common_base(
    index: CppClassIndex,
    class1: str,
    class2: str
) -> Optional[str]:
    """
    查找两个类的共同基类

    参数：
        index: 类索引
        class1: 类1
        class2: 类2

    返回：
        共同基类，如果不存在返回 None
    """
    mro1 = set(compute_mro(index, class1))
    mro2 = compute_mro(index, class2)

    for name in mro2:
        if name in mro1:
            return name

    return None
