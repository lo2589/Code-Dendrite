"""
基础代码分析器接口
所有语言分析器都必须实现这个基类
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
import os


@dataclass
class FunctionInfo:
    """函数信息"""
    name: str
    file_path: str
    line_number: int
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    calls: List[str] = field(default_factory=list)
    is_async: bool = False
    is_method: bool = False
    class_name: Optional[str] = None
    # Qualified lexical parent for nested JS/TS functions.  This is separate
    # from class_name: a nested function is not a method and must not create a
    # fake class container in the Anchor graph.
    parent_function: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    line_end: int = 0
    column_start: int = 0
    column_end: int = 0
    call_sites: List[dict] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        if self.class_name:
            return f"{self.class_name}.{self.name}"
        if self.parent_function:
            return f"{self.parent_function}.{self.name}"
        return self.name

    @property
    def signature(self) -> str:
        params = ", ".join(self.parameters)
        return f"{self.full_name}({params})"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "full_name": self.full_name,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "parameters": self.parameters,
            "return_type": self.return_type,
            "calls": self.calls,
            "is_async": self.is_async,
            "is_method": self.is_method,
            "class_name": self.class_name,
            "parent_function": self.parent_function,
            "decorators": self.decorators,
            "line_end": self.line_end,
            "column_start": self.column_start,
            "column_end": self.column_end,
            "call_sites": self.call_sites,
        }


@dataclass
class ModuleInfo:
    """模块信息（顶级代码块）"""
    name: str
    file_path: str
    line_number: int
    functions: List[FunctionInfo] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    top_level_calls: List[str] = field(default_factory=list)


@dataclass
class ProjectInfo:
    """项目信息"""
    root_path: str
    language: str
    files: List[str] = field(default_factory=list)
    modules: List[ModuleInfo] = field(default_factory=list)
    functions: List[FunctionInfo] = field(default_factory=list)
    call_graph: Dict[str, List[str]] = field(default_factory=dict)
    function_map: Dict[str, List[FunctionInfo]] = field(default_factory=dict)
    ui_events: List[Dict] = field(default_factory=list)
    message_commands: Dict[str, int] = field(default_factory=dict)

    def get_function(self, name: str) -> Optional[FunctionInfo]:
        for func in self.functions:
            if func.full_name == name or func.name == name:
                return func
        return None

    def get_functions_by_file(self, file_path: str) -> List[FunctionInfo]:
        return [f for f in self.functions if f.file_path == file_path]

    def get_callers(self, func_name: str) -> List[str]:
        callers = []
        for caller, callees in self.call_graph.items():
            if func_name in callees:
                callers.append(caller)
        return callers

    def get_callees(self, func_name: str) -> List[str]:
        return self.call_graph.get(func_name, [])

    def to_dict(self) -> dict:
        return {
            "root_path": self.root_path,
            "language": self.language,
            "files": self.files,
            "functions": [f.to_dict() for f in self.functions],
            "call_graph": self.call_graph,
            "statistics": {
                "total_files": len(self.files),
                "total_functions": len(self.functions),
                "total_calls": sum(len(calls) for calls in self.call_graph.values()),
            }
        }


class BaseAnalyzer(ABC):
    """代码分析器基类"""

    def __init__(self, root_path: str):
        self.root_path = root_path
        self.files: List[str] = []
        self.modules: List[ModuleInfo] = []
        self.functions: List[FunctionInfo] = []
        self.call_graph: Dict[str, List[str]] = {}
        self.function_map: Dict[str, List[FunctionInfo]] = {}

    @property
    @abstractmethod
    def language_name(self) -> str:
        """返回语言名称"""
        pass

    @abstractmethod
    def is_supported_file(self, file_path: str) -> bool:
        """判断是否是支持的文件"""
        pass

    @abstractmethod
    def analyze_file(self, file_path: str) -> ModuleInfo:
        """分析单个文件"""
        pass

    def scan_files(self) -> List[str]:
        """扫描项目中的所有文件"""
        files = []
        for root, dirs, filenames in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules', 'venv', '.venv', 'build', 'dist']]
            for filename in filenames:
                file_path = os.path.join(root, filename)
                if self.is_supported_file(file_path):
                    files.append(file_path)
        return files

    def analyze(self) -> ProjectInfo:
        """分析整个项目"""
        self.files = self.scan_files()

        for file_path in self.files:
            module_info = self.analyze_file(file_path)
            self.modules.append(module_info)
            self.functions.extend(module_info.functions)

        self._build_function_map()
        self._build_call_graph()

        return ProjectInfo(
            root_path=self.root_path,
            language=self.language_name,
            files=self.files,
            modules=self.modules,
            functions=self.functions,
            call_graph=self.call_graph,
            function_map=self.function_map
        )

    def _build_function_map(self):
        """建立函数名到函数的映射"""
        for func in self.functions:
            if func.full_name not in self.function_map:
                self.function_map[func.full_name] = []
            self.function_map[func.full_name].append(func)

    def _build_call_graph(self):
        """建立调用关系图"""
        for func in self.functions:
            if func.calls:
                resolved_calls = self._resolve_calls(func)
                if resolved_calls:
                    self.call_graph[func.full_name] = resolved_calls

    def _resolve_calls(self, func: FunctionInfo) -> List[str]:
        """解析函数调用，建立跨文件调用关系"""
        resolved = []
        for call in func.calls:
            if call in self.function_map:
                for target_func in self.function_map[call]:
                    resolved.append(target_func.full_name)
            else:
                matched = self._find_function_by_short_name(call)
                if matched:
                    resolved.append(matched.full_name)
                else:
                    resolved.append(call)
        return list(set(resolved))

    def _find_function_by_short_name(self, name: str) -> Optional[FunctionInfo]:
        """通过短函数名查找函数"""
        for func in self.functions:
            if func.name == name:
                return func
        return None
