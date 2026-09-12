"""
types.py - L3_Inheritance 数据类型定义
=======================================
从TypeScript迁移的数据结构。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class MethodInfo:
    """方法信息"""
    name: str
    start_line: int
    end_line: int
    has_super: bool                    # 是否调用super()
    decorators: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "has_super": self.has_super,
            "decorators": self.decorators
        }


@dataclass
class ClassInfo:
    """类信息（文件内解析结果）"""
    name: str
    bases: List[str]                   # 基类名列表
    methods: List[MethodInfo]
    file: str
    line: int
    decorators: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "bases": self.bases,
            "methods": [m.to_dict() for m in self.methods],
            "file": self.file,
            "line": self.line,
            "decorators": self.decorators
        }


@dataclass
class ImportInfo:
    """导入信息"""
    module: str                        # import的模块名
    aliases: Dict[str, str]            # 原名 -> 别名
    from_path: Optional[str]           # from xxx import 的xxx
    line: int
    
    def to_dict(self) -> dict:
        return {
            "module": self.module,
            "aliases": self.aliases,
            "from_path": self.from_path,
            "line": self.line
        }


@dataclass
class PythonFileInfo:
    """Python文件解析结果"""
    classes: List[ClassInfo]
    imports: List[ImportInfo]
    
    def to_dict(self) -> dict:
        return {
            "classes": [c.to_dict() for c in self.classes],
            "imports": [i.to_dict() for i in self.imports]
        }


@dataclass
class ClassEntry:
    """类索引条目（继承链中的节点）"""
    name: str
    file: str
    line: int
    bases: List[str]
    methods: List[MethodInfo]
    imports: List[ImportInfo]
    depth: int                         # 继承深度
    is_external: bool
    module: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "file": self.file,
            "line": self.line,
            "bases": self.bases,
            "methods": [m.to_dict() for m in self.methods],
            "depth": self.depth,
            "is_external": self.is_external,
            "module": self.module
        }


@dataclass
class ExternalClassEntry:
    """外部库类条目"""
    name: str
    file: str                          # 如 "[builtin]" 或实际路径
    line: int
    bases: List[str]
    module: str
    is_external: bool = True
    methods: List[MethodInfo] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "file": self.file,
            "line": self.line,
            "bases": self.bases,
            "module": self.module,
            "is_external": self.is_external
        }


@dataclass
class Location:
    """代码位置"""
    file: str
    line: int
    column: int = 0
    
    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "column": self.column
        }


class ClassIndex:
    """
    类索引
    
    维护项目中所有类的信息，支持快速查找。
    """
    
    def __init__(self):
        self.classes: Dict[str, ClassEntry] = {}
        self.classes_fq: Dict[str, ClassEntry] = {}  # "file::name" -> entry, collision-free
        self.file_imports: Dict[str, List[ImportInfo]] = {}
        self.file_classes: Dict[str, List[str]] = {}  # file -> [class_names]

    def add_class(self, entry: ClassEntry):
        """添加类到索引"""
        self.classes[entry.name] = entry
        self.classes_fq["{}::{}".format(entry.file, entry.name)] = entry

        # 维护文件->类映射
        if entry.file not in self.file_classes:
            self.file_classes[entry.file] = []
        if entry.name not in self.file_classes[entry.file]:
            self.file_classes[entry.file].append(entry.name)
    
    def get_class(self, name: str) -> Optional[ClassEntry]:
        """获取类"""
        return self.classes.get(name)
    
    def get_classes_in_file(self, file_path: str) -> List[ClassEntry]:
        """获取文件中的所有类"""
        class_names = self.file_classes.get(file_path, [])
        return [self.classes_fq["{}::{}".format(file_path, n)]
                for n in class_names
                if "{}::{}".format(file_path, n) in self.classes_fq]
    
    def get_imports(self, file_path: str) -> List[ImportInfo]:
        """获取文件的导入信息"""
        return self.file_imports.get(file_path, [])
    
    def __contains__(self, name: str) -> bool:
        return name in self.classes
    
    def __len__(self) -> int:
        return len(self.classes)
    
    def to_dict(self) -> dict:
        return {
            "classes": {k: v.to_dict() for k, v in self.classes.items()},
            "total": len(self.classes)
        }
