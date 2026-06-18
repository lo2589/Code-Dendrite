"""
resolver.py - 继承链解析器 (Hard L3-003, L3-004, L3-008, L3-009)
==================================================================
核心继承链追踪逻辑。

对应TS: inheritanceResolver.ts
"""

from pathlib import PurePosixPath
from typing import List, Optional, Union, Set, Dict, Any

from .types import (
    ClassIndex, ClassEntry, ExternalClassEntry,
    ImportInfo, Location, MethodInfo
)
from .external_lib import resolve_external_class, get_builtin_class_info


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


def resolve_inheritance(
    class_name: str,
    index: ClassIndex,
    max_depth: int = 10
) -> List[Union[ClassEntry, ExternalClassEntry]]:
    """
    解析类的完整继承链 (Hard L3-003)
    
    参数:
        class_name: 类名
        index: 类索引
        max_depth: 最大追踪深度
    
    返回:
        继承链列表（从子类到根类）
    
    对应TS: inheritanceResolver.ts 的 resolveInheritanceEnhanced()
    
    核心逻辑:
        1. 从类索引中查找类
        2. 获取其基类列表
        3. 递归解析每个基类:
           - 工作区内类: 继续递归
           - 外部库类: 调用resolve_external_class
           - 内置类: 调用get_builtin_class_info
        4. 直到到达object或达到最大深度
    
    多继承处理:
        - 按顺序解析所有基类
        - 返回主继承链（第一个基类的链）
    """
    chain: List[Union[ClassEntry, ExternalClassEntry]] = []
    visited: Set[str] = set()
    
    _resolve_recursive(class_name, index, chain, visited, 0, max_depth)
    
    return chain


def _resolve_recursive(
    class_name: str,
    index: ClassIndex,
    chain: List[Union[ClassEntry, ExternalClassEntry]],
    visited: Set[str],
    depth: int,
    max_depth: int
):
    """递归解析继承链"""
    if depth >= max_depth:
        return
    
    if class_name in visited:
        return  # 避免循环
    
    visited.add(class_name)
    
    # 1. 检查工作区索引
    if class_name in index.classes:
        entry = index.classes[class_name]
        # 更新深度
        entry_copy = ClassEntry(
            name=entry.name,
            file=entry.file,
            line=entry.line,
            bases=entry.bases,
            methods=entry.methods,
            imports=entry.imports,
            depth=depth,
            is_external=False,
            module=entry.module
        )
        chain.append(entry_copy)
        
        if not entry.bases:
            # 没有基类，到达顶端
            return
        
        # 解析第一个基类（主继承链）
        base_name = entry.bases[0]
        
        # 处理Generic[T]等泛型基类
        if '[' in base_name:
            base_name = base_name.split('[')[0]
        
        resolved = resolve_base_class(base_name, entry.file, entry.imports, index)
        
        if resolved:
            if isinstance(resolved, ExternalClassEntry):
                resolved_copy = ExternalClassEntry(
                    name=resolved.name,
                    file=resolved.file,
                    line=resolved.line,
                    bases=resolved.bases,
                    module=resolved.module,
                    methods=resolved.methods
                )
                chain.append(resolved_copy)
                
                # 继续追踪外部类的基类
                if resolved.bases:
                    for base in resolved.bases:
                        _resolve_recursive(base, index, chain, visited, depth + 1, max_depth)
            else:
                _resolve_recursive(resolved.name, index, chain, visited, depth + 1, max_depth)
        else:
            # 尝试内置类
            builtin = get_builtin_class_info(base_name)
            if builtin:
                chain.append(builtin)
                if builtin.bases:
                    for base in builtin.bases:
                        _resolve_recursive(base, index, chain, visited, depth + 1, max_depth)
    
    # 2. 检查内置类
    else:
        builtin = get_builtin_class_info(class_name)
        if builtin:
            chain.append(builtin)
            if builtin.bases:
                for base in builtin.bases:
                    _resolve_recursive(base, index, chain, visited, depth + 1, max_depth)


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


def compute_mro(class_name: str, index: ClassIndex) -> List[str]:
    """
    计算MRO（方法解析顺序）(Hard L3-008)
    
    参数:
        class_name: 类名
        index: 类索引
    
    返回:
        MRO列表（类名字符串）
    
    实现: C3线性化算法
    
    对于多继承:
        class C(A, B): pass
        MRO = [C] + merge(mro(A), mro(B), [A, B])
    
    merge规则:
        1. 取第一个列表的第一个元素
        2. 如果该元素不在其他列表的尾部，则输出它并从所有列表中移除
        3. 否则，跳过当前列表，检查下一个
        4. 重复直到所有列表为空
    """
    # 简化实现：使用继承链
    chain = resolve_inheritance(class_name, index)
    return [entry.name for entry in chain]


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


def find_method_origin(
    class_name: str,
    method_name: str,
    index: ClassIndex
) -> Optional[Location]:
    """
    查找方法的原始定义位置 (Hard L3-009)
    
    参数:
        class_name: 类名
        method_name: 方法名
        index: 类索引
    
    返回:
        Location对象，未找到返回None
    
    沿MRO查找第一个定义该方法的类。
    """
    chain = resolve_inheritance(class_name, index)
    
    for entry in chain:
        for method in entry.methods:
            if method.name == method_name:
                return Location(
                    file=entry.file,
                    line=method.start_line
                )
    
    return None


def find_method_origin_with_class(
    class_name: str,
    method_name: str,
    index: ClassIndex
) -> Optional[Dict]:
    """
    查找方法定义位置（包含类名）
    
    参数:
        class_name: 类名
        method_name: 方法名
        index: 类索引
    
    返回:
        {"class": str, "file": str, "line": int}
    """
    chain = resolve_inheritance(class_name, index)
    
    for entry in chain:
        for method in entry.methods:
            if method.name == method_name:
                return {
                    "class": entry.name,
                    "file": entry.file,
                    "line": method.start_line
                }
    
    return None


def get_overridden_methods(
    class_name: str,
    index: ClassIndex
) -> List[dict]:
    """
    获取类中所有重写的方法
    
    返回:
        [{"method": str, "overrides": str, "location": Location}, ...]
    """
    if class_name not in index.classes:
        return []
    
    entry = index.classes[class_name]
    chain = resolve_inheritance(class_name, index)
    
    if len(chain) < 2:
        return []  # 没有基类
    
    result = []
    
    for method in entry.methods:
        # 检查是否在基类中定义
        for parent in chain[1:]:
            if isinstance(parent, ExternalClassEntry):
                parent_methods = [m.name for m in parent.methods] if parent.methods else []
            else:
                parent_methods = [m.name for m in parent.methods]
            
            if method.name in parent_methods:
                result.append({
                    "method": method.name,
                    "overrides": parent.name,
                    "location": Location(file=entry.file, line=method.start_line)
                })
                break
    
    return result


def find_all_subclasses(
    class_name: str,
    index: ClassIndex
) -> List[ClassEntry]:
    """
    查找类的所有子类
    
    参数:
        class_name: 类名
        index: 类索引
    
    返回:
        子类列表
    """
    subclasses = []
    
    for entry in index.classes.values():
        if class_name in entry.bases:
            subclasses.append(entry)
    
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


def find_method_in_chain(
    chain: List[Union[ClassEntry, ExternalClassEntry]],
    method_name: str
) -> Optional[Location]:
    """
    在继承链中查找方法定义
    
    参数:
        chain: 继承链
        method_name: 方法名
    
    返回:
        方法定义位置，未找到返回 None
    """
    for entry in chain:
        for method in entry.methods:
            if method.name == method_name:
                return Location(
                    file=entry.file,
                    line=method.start_line
                )
    
    return None


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
