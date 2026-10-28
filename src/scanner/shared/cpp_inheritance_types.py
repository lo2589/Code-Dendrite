"""
types.py - C++ 继承类型定义
============================
C++ 继承追踪系统的类型定义。
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class CppMethodInfo:
    """C++ 方法信息"""
    name: str
    start_line: int
    end_line: int
    is_virtual: bool = False
    is_override: bool = False
    is_pure_virtual: bool = False
    is_static: bool = False
    is_const: bool = False
    access: str = "public"
    return_type: str = ""
    parameters: List[str] = field(default_factory=list)
    template_params: List[str] = field(default_factory=list)
    is_implementation: bool = False
    impl_file: Optional[str] = None


@dataclass
class CppClassInfo:
    """C++ 类信息"""
    name: str
    file: str
    line: int
    bases: List[str]
    methods: List[CppMethodInfo] = field(default_factory=list)
    templates: List[str] = field(default_factory=list)
    is_struct: bool = False
    is_template: bool = False
    is_external: bool = False
    module: Optional[str] = None
    depth: int = 0


@dataclass
class CppIncludeInfo:
    """C++ include 信息"""
    path: str
    is_system: bool
    line: int


@dataclass
class CppNamespaceInfo:
    """命名空间信息"""
    name: str
    line: int
    classes: List[str] = field(default_factory=list)


@dataclass
class CppFileInfo:
    """C++ 文件信息"""
    file_path: str
    includes: List[CppIncludeInfo] = field(default_factory=list)
    classes: List[CppClassInfo] = field(default_factory=list)
    namespaces: List[CppNamespaceInfo] = field(default_factory=list)
    line_count: int = 0


@dataclass
class CppLocation:
    """位置信息"""
    file: str
    line: int
    column: int = 0


@dataclass
class CppInheritanceEntry:
    """C++ 继承条目"""
    name: str
    file: str
    line: int
    bases: List[str]
    methods: List[CppMethodInfo]
    depth: int
    is_external: bool = False
    module: Optional[str] = None


class CppClassIndex:
    """C++ 类索引"""

    def __init__(self):
        self.classes: Dict[str, CppClassInfo] = {}
        self.file_classes: Dict[str, List[str]] = {}
        self.namespace_classes: Dict[str, List[str]] = {}
        self._lock = False

    def add(self, class_info: CppClassInfo):
        """添加类到索引"""
        self.classes[class_info.name] = class_info

        if class_info.file not in self.file_classes:
            self.file_classes[class_info.file] = []
        self.file_classes[class_info.file].append(class_info.name)

    def get(self, name: str) -> Optional[CppClassInfo]:
        """获取类信息"""
        return self.classes.get(name)

    def get_by_file(self, file_path: str) -> List[CppClassInfo]:
        """获取文件中的所有类"""
        class_names = self.file_classes.get(file_path, [])
        return [self.classes[name] for name in class_names if name in self.classes]

    def get_by_namespace(self, namespace: str) -> List[CppClassInfo]:
        """获取命名空间中的所有类"""
        class_names = self.namespace_classes.get(namespace, [])
        return [self.classes[name] for name in class_names if name in self.classes]

    def __len__(self) -> int:
        return len(self.classes)

    def __contains__(self, name: str) -> bool:
        return name in self.classes

    def items(self):
        return self.classes.items()

    def keys(self):
        return self.classes.keys()

    def values(self):
        return self.classes.values()


@dataclass
class CppExternalClassEntry:
    """C++ 外部库类条目"""
    name: str
    file: str
    line: int
    bases: List[str]
    module: str
    methods: List[CppMethodInfo] = field(default_factory=list)
    is_external: bool = True


@dataclass
class CppSuperCallInfo:
    """C++ super() 调用信息（通过模板实现）"""
    class_name: str
    method_name: str
    base_class: str
    file: str
    line: int


@dataclass
class CppOverrideInfo:
    """C++ override 信息"""
    class_name: str
    method_name: str
    base_method: str
    base_class: str
    file: str
    line: int
