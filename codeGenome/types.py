"""
codeGenome/types.py - 统一的数据类型定义
=========================================
代码基因组系统的核心类型定义，支持 Python 和 C++。

锚点命名规范:
    {lang}.{module}.{category}.{name}

示例:
    py.main.imports.os              # import os
    py.main.assigns.VERSION        # VERSION = "1.0"
    py.main.__main__.block_1        # if __name__ == "__main__" 块
    py.main.classes.App              # class App
    py.main.classes.App.methods.run # class App.run()

    cpp.main.includes.vector        # #include <vector>
    cpp.main.namespaces.ns.vars.g   # 全局变量
    cpp.main.classes.Robot          # class Robot
    cpp.main.classes.Robot.methods.init
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class Language(Enum):
    """支持的编程语言"""
    PYTHON = "py"
    CPP = "cpp"


class AnchorCategory(Enum):
    """锚点类别"""
    IMPORT = "imports"
    ASSIGN = "assigns"
    STATEMENT = "statements"
    CLASS = "classes"
    STRUCT = "structs"
    FUNCTION = "functions"
    METHOD = "methods"
    NAMESPACE = "namespaces"
    VARIABLE = "vars"
    ENUM = "enums"
    MAIN_BLOCK = "__main__"
    INCLUDE = "includes"
    USING = "usings"


@dataclass
class CodeAnchor:
    """
    代码锚点 - 代码基因组的基本单位

    属性:
        id: 唯一标识符，格式: {lang}.{module}.{category}.{name}
        language: 编程语言 (py/cpp)
        category: 锚点类别
        file: 文件路径
        line_start: 起始行号
        line_end: 结束行号
        name: 锚点名称（不含路径）
        code: 源代码内容
        hash: 内容哈希值
        parent_id: 父锚点 ID（如果有）
        children_ids: 子锚点 ID 列表
        metadata: 额外元数据
    """
    id: str
    language: str
    category: str
    file: str
    line_start: int
    line_end: int
    name: str
    code: str
    hash: str
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.parent_id is None:
            self.parent_id = ""
        if self.children_ids is None:
            self.children_ids = []
        if self.metadata is None:
            self.metadata = {}

    @property
    def is_import(self) -> bool:
        return self.category in (AnchorCategory.IMPORT.value, AnchorCategory.INCLUDE.value)

    @property
    def is_class(self) -> bool:
        return self.category in (AnchorCategory.CLASS.value, AnchorCategory.STRUCT.value)

    @property
    def is_function(self) -> bool:
        return self.category in (AnchorCategory.FUNCTION.value, AnchorCategory.METHOD.value)

    @property
    def is_main_block(self) -> bool:
        return self.category == AnchorCategory.MAIN_BLOCK.value

    @property
    def is_top_level(self) -> bool:
        return self.category in (
            AnchorCategory.IMPORT.value,
            AnchorCategory.ASSIGN.value,
            AnchorCategory.STATEMENT.value,
            AnchorCategory.MAIN_BLOCK.value
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "language": self.language,
            "category": self.category,
            "file": self.file,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "name": self.name,
            "code": self.code,
            "hash": self.hash,
            "parent_id": self.parent_id or "",
            "children_ids": self.children_ids or [],
            "metadata": self.metadata or {}
        }

    def get_location(self) -> str:
        return f"{self.file}:{self.line_start}-{self.line_end}"


@dataclass
class AnchorIndex:
    """
    锚点索引 - 包含所有锚点的索引结构
    """
    anchors: Dict[str, CodeAnchor] = field(default_factory=dict)
    file_anchors: Dict[str, List[str]] = field(default_factory=lambda: {})
    category_anchors: Dict[str, List[str]] = field(default_factory=lambda: {})
    hash_to_id: Dict[str, str] = field(default_factory=dict)
    parse_failures: List[dict] = field(default_factory=list)
    auto_fixed: List[dict] = field(default_factory=list)

    def __post_init__(self):
        if self.anchors is None:
            self.anchors = {}
        if self.file_anchors is None:
            self.file_anchors = {}
        if self.category_anchors is None:
            self.category_anchors = {}
        if self.hash_to_id is None:
            self.hash_to_id = {}
        if self.parse_failures is None:
            self.parse_failures = []
        if self.auto_fixed is None:
            self.auto_fixed = []

    def add(self, anchor: CodeAnchor):
        self.anchors[anchor.id] = anchor

        if anchor.file not in self.file_anchors:
            self.file_anchors[anchor.file] = []
        self.file_anchors[anchor.file].append(anchor.id)

        if anchor.category not in self.category_anchors:
            self.category_anchors[anchor.category] = []
        self.category_anchors[anchor.category].append(anchor.id)

        self.hash_to_id[anchor.hash] = anchor.id

    def get(self, anchor_id: str) -> Optional[CodeAnchor]:
        return self.anchors.get(anchor_id)

    def get_by_hash(self, hash_val: str) -> Optional[CodeAnchor]:
        anchor_id = self.hash_to_id.get(hash_val)
        return self.anchors.get(anchor_id) if anchor_id else None

    def get_by_file(self, file: str) -> List[CodeAnchor]:
        anchor_ids = self.file_anchors.get(file, [])
        return [self.anchors[a] for a in anchor_ids if a in self.anchors]

    def get_by_category(self, category: str) -> List[CodeAnchor]:
        anchor_ids = self.category_anchors.get(category, [])
        return [self.anchors[a] for a in anchor_ids if a in self.anchors]

    def get_children(self, anchor_id: str) -> List[CodeAnchor]:
        anchor = self.anchors.get(anchor_id)
        if not anchor:
            return []
        return [self.anchors[c] for c in anchor.children_ids if c in self.anchors]

    def get_parent(self, anchor_id: str) -> Optional[CodeAnchor]:
        anchor = self.anchors.get(anchor_id)
        if not anchor or not anchor.parent_id:
            return None
        return self.anchors.get(anchor.parent_id)

    def __len__(self) -> int:
        return len(self.anchors)

    def get_stats(self) -> dict:
        return {
            "total": len(self.anchors),
            "by_category": {cat: len(ids) for cat, ids in self.category_anchors.items()},
            "by_language": self._count_by_language(),
            "files": len(self.file_anchors)
        }

    def _count_by_language(self) -> dict:
        langs = {}
        for anchor in self.anchors.values():
            langs[anchor.language] = langs.get(anchor.language, 0) + 1
        return langs


@dataclass
class ImportInfo:
    """导入信息"""
    name: str
    module: str
    alias: Optional[str] = None
    is_from: bool = False
    imported_names: List[str] = field(default_factory=list)


@dataclass
class ClassInfo:
    """类信息"""
    name: str
    bases: List[str] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    is_struct: bool = False


@dataclass
class FunctionInfo:
    """函数信息"""
    name: str
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    is_method: bool = False
    is_static: bool = False
    is_async: bool = False


@dataclass
class TopLevelBlock:
    """顶层代码块"""
    type: str
    code: str
    line_start: int
    line_end: int
    is_main_guard: bool = False
    statements: List[str] = field(default_factory=list)
