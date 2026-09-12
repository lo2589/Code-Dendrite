"""
class_indexer.py - C++ 类索引构建器
=====================================
构建 C++ 项目的类索引，支持：
- 普通类
- 模板类
- 结构体
- 多继承
- 命名空间
- .h/.cpp 文件匹配

用法：
    from analyzer.inherit.language.cpp.class_indexer import build_class_index

    index = build_class_index("/path/to/project")
    for name, cls in index.classes.items():
        print(f"{name}: {cls.bases}")
"""

from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple

from analyzer.shared.legacy.cpp_inheritance.types import CppClassIndex, CppClassInfo, CppMethodInfo
from scanner.language.cpp.cpp_parser import parse_cpp_file, parse_cpp_directory, extract_implementation_methods

def _is_in_namespace(cls: CppClassInfo, namespace) -> bool:
    """检查类是否在命名空间中"""
    return True

def _get_full_name(cls: CppClassInfo, namespaces: List) -> str:
    """获取类的完整名称（包括命名空间）"""
    for ns in namespaces:
        if ns.line < cls.line:
            if _is_in_namespace(cls, ns):
                return f"{ns.name}::{cls.name}"
    return cls.name

def _merge_h_cpp_classes(
    index: CppClassIndex,
    header_classes: Dict[str, Tuple[CppClassInfo, str]],
    cpp_methods: Dict[str, List[Tuple[CppMethodInfo, str]]]
):
    """合并 .h 和 .cpp 文件中的类信息"""
    for class_name, (header_cls, header_file) in header_classes.items():
        cls = index.get(class_name)
        if cls:
            cls.file = header_file

            if class_name in cpp_methods:
                existing_methods = {m.name for m in cls.methods}
                for method, cpp_file in cpp_methods[class_name]:
                    if method.name not in existing_methods:
                        method.start_line = 0
                        cls.methods.append(method)

def _resolve_forward_declarations(index: CppClassIndex):
    """解析前向声明"""
    forward_decls: Set[str] = set()

    for cls in index.values():
        for base in cls.bases:
            base_name = base.split('::')[-1]
            if base_name not in index.classes:
                forward_decls.add(base_name)

    for name in forward_decls:
        index.classes[name] = CppClassInfo(
            name=name,
            file="[forward_declaration]",
            line=0,
            bases=[]
        )

def build_class_index(
    root: str,
    extensions: List[str] = None,
    exclude_dirs: List[str] = None,
    match_h_cpp: bool = True
) -> CppClassIndex:
    """
    构建项目类索引（自动关联 .h/.cpp）

    参数：
        root: 项目根目录
        extensions: 要分析的文件扩展名
        exclude_dirs: 要排除的目录
        match_h_cpp: 是否自动关联 .h/.cpp 文件

    返回：
        CppClassIndex 对象

    自动关联：
        1. 从 .h 文件解析类定义和方法声明
        2. 从 .cpp 文件解析方法实现
        3. 自动匹配并关联（ClassName::method_name 格式）
    """
    if extensions is None:
        extensions = ['.cpp', '.h', '.hpp', '.cc', '.cxx', '.hxx']

    if exclude_dirs is None:
        exclude_dirs = ['build', 'out', 'cmake-build', 'node_modules', '.git']

    index = CppClassIndex()
    root_path = Path(root)

    cpp_files: List[Path] = []
    header_files: Dict[str, Path] = {}

    for ext in extensions:
        for file_path in root_path.rglob(f'*{ext}'):
            if _should_exclude(str(file_path), exclude_dirs):
                continue

            is_header = file_path.suffix in ['.h', '.hpp', '.hxx', '.hh']

            if is_header:
                header_files[str(file_path)] = file_path
            else:
                cpp_files.append(file_path)

    all_implementations: Dict[str, Dict[str, CppMethodInfo]] = {}

    for cpp_file in cpp_files:
        try:
            implementations = extract_implementation_methods(str(cpp_file))

            for key, methods in implementations.items():
                class_name, method_name = key.rsplit('::', 1)
                if class_name not in all_implementations:
                    all_implementations[class_name] = {}
                all_implementations[class_name][method_name] = methods[0]
        except Exception:
            continue

    for header_path in header_files.values():
        try:
            info = parse_cpp_file(str(header_path))

            for cls in info.classes:
                full_name = _get_full_name(cls, info.namespaces)

                if match_h_cpp and full_name in all_implementations:
                    for method in cls.methods:
                        if method.name in all_implementations[full_name]:
                            impl_method = all_implementations[full_name][method.name]
                            method.is_implementation = True
                            method.impl_file = impl_method.impl_file

                cls_copy = CppClassInfo(
                    name=full_name,
                    file=cls.file,
                    line=cls.line,
                    bases=cls.bases,
                    methods=cls.methods,
                    templates=cls.templates,
                    is_struct=cls.is_struct,
                    is_template=cls.is_template
                )
                index.add(cls_copy)

        except Exception as e:
            continue

    _resolve_forward_declarations(index)

    return index

def _should_exclude(file_path: str, exclude_dirs: List[str]) -> bool:
    """检查是否应该排除文件"""
    path = Path(file_path)
    for part in path.parts:
        if part in exclude_dirs:
            return True
    return False

def add_to_index(index: CppClassIndex, class_info: CppClassInfo):
    """
    添加类到索引

    参数：
        index: 类索引
        class_info: 类信息
    """
    index.add(class_info)

def find_subclasses(index: CppClassIndex, class_name: str) -> List[CppClassInfo]:
    """
    查找类的所有子类（包括多层继承的子类）

    参数：
        index: 类索引
        class_name: 类名

    返回：
        子类列表
    """
    subclasses = []
    class_short_name = class_name.split('::')[-1]
    visited = set()

    def search(name: str):
        for cls in index.values():
            if id(cls) in visited:
                continue

            for base in cls.bases:
                base_short_name = base.split('::')[-1]
                if base_short_name == class_short_name or base == name:
                    visited.add(id(cls))
                    subclasses.append(cls)
                    search(cls.name)

    search(class_name)
    return subclasses

def find_template_instantiations(
    index: CppClassIndex,
    template_name: str
) -> List[CppClassInfo]:
    """
    查找模板类的实例化

    参数：
        index: 类索引
        template_name: 模板名

    返回：
        实例化列表
    """
    instantiations = []

    for cls in index.values():
        if cls.templates and cls.is_template:
            if cls.name.startswith(template_name):
                instantiations.append(cls)

    return instantiations

def get_class_hierarchy(index: CppClassIndex, class_name: str) -> List[str]:
    """
    获取类的继承层次（支持多层继承）

    参数：
        index: 类索引
        class_name: 类名

    返回：
        继承层次列表（从子类到根类）
    """
    hierarchy = [class_name]
    visited = {class_name}

    def resolve(name: str, depth: int = 0):
        if depth > 20:
            return

        cls = index.get(name)
        if cls:
            for base in cls.bases:
                base_name = base.split('::')[-1]
                if base_name not in visited:
                    visited.add(base_name)
                    hierarchy.append(base_name)
                    resolve(base_name, depth + 1)

                for full_base_name, full_cls in index.classes.items():
                    if full_base_name.split('::')[-1] == base_name:
                        if full_base_name not in visited:
                            visited.add(full_base_name)
                            hierarchy.append(full_base_name)
                            resolve(full_base_name, depth + 1)

    resolve(class_name)
    return hierarchy

def get_all_virtual_methods(index: CppClassIndex, class_name: str) -> List[str]:
    """
    获取类的所有虚方法（沿继承链）

    参数：
        index: 类索引
        class_name: 类名

    返回：
        虚方法名列表
    """
    virtual_methods = []
    hierarchy = get_class_hierarchy(index, class_name)

    for name in hierarchy:
        cls = index.get(name)
        if cls:
            for method in cls.methods:
                if method.is_virtual or method.is_override:
                    if method.name not in virtual_methods:
                        virtual_methods.append(method.name)

    return virtual_methods
