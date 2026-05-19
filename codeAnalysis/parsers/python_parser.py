"""
Python 代码解析器
使用 Python 内置的 ast 模块分析代码
"""

import ast
import os
from typing import List, Dict, Set, Optional, Any
from dataclasses import dataclass, field


@dataclass
class FunctionInfo:
    """函数信息"""
    name: str
    file: str
    line: int
    end_line: int
    params: List[str]
    returns: Optional[str]
    calls: List[str] = field(default_factory=list)
    called_by: List[str] = field(default_factory=list)
    docstring: str = ""
    is_class_method: bool = False
    class_name: Optional[str] = None


@dataclass
class ModuleInfo:
    """模块信息（未包装成函数的代码块）"""
    name: str
    file: str
    line: int
    end_line: int
    description: str = ""
    imports: List[str] = field(default_factory=list)


@dataclass
class ImportInfo:
    """导入信息"""
    module: str
    names: List[str]
    line: int
    is_from: bool = False


class PythonParser:
    """Python 代码解析器"""

    def __init__(self):
        self.functions: List[FunctionInfo] = []
        self.modules: List[ModuleInfo] = []
        self.imports: List[ImportInfo] = []
        self.call_graph: Dict[str, List[str]] = {}  # func -> [called_funcs]
        self.reverse_graph: Dict[str, List[str]] = {}  # func -> [callers]

    def parse_file(self, file_path: str) -> None:
        """解析单个 Python 文件"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            print(f"⚠️ 语法错误 {file_path}:{e.lineno} - {e.msg}")
            return

        module_name = os.path.splitext(os.path.basename(file_path))[0]
        visitor = FunctionVisitor(module_name, file_path)
        visitor.visit(tree)

        self.functions.extend(visitor.functions)
        self.modules.extend(visitor.modules)
        self.imports.extend(visitor.imports)

        for func in visitor.functions:
            self.call_graph[func.name] = func.calls

    def parse_directory(self, dir_path: str, include_patterns: List[str] = None) -> None:
        """递归解析目录下所有 Python 文件"""
        if include_patterns is None:
            include_patterns = ['*.py']

        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'venv', 'env', 'node_modules']]

            for file in files:
                if any(file.endswith(ext.replace('*', '')) for ext in include_patterns):
                    file_path = os.path.join(root, file)
                    self.parse_file(file_path)

        self._build_reverse_graph()

    def _build_reverse_graph(self) -> None:
        """构建反向调用图"""
        for func_name, calls in self.call_graph.items():
            for called in calls:
                if called not in self.reverse_graph:
                    self.reverse_graph[called] = []
                if func_name not in self.reverse_graph[called]:
                    self.reverse_graph[called].append(func_name)

        for func in self.functions:
            func.called_by = self.reverse_graph.get(func.name, [])

    def get_call_graph_json(self) -> Dict[str, Any]:
        """生成 AI 友好的 JSON 格式"""
        return {
            "functions": [
                {
                    "name": f.name,
                    "full_name": f"{f.class_name}.{f.name}" if f.class_name else f.name,
                    "file": f.file,
                    "line": f.line,
                    "end_line": f.end_line,
                    "params": f.params,
                    "returns": f.returns,
                    "calls": f.calls,
                    "called_by": f.called_by,
                    "docstring": f.docstring[:100] if f.docstring else "",
                    "is_method": f.is_class_method
                }
                for f in self.functions
            ],
            "modules": [
                {
                    "name": m.name,
                    "file": m.file,
                    "line": m.line,
                    "description": m.description
                }
                for m in self.modules
            ],
            "statistics": {
                "total_functions": len(self.functions),
                "total_modules": len(self.modules),
                "total_calls": sum(len(calls) for calls in self.call_graph.values())
            }
        }


class FunctionVisitor(ast.NodeVisitor):
    """AST 访问器，收集函数信息"""

    def __init__(self, module_name: str, file_path: str):
        self.module_name = module_name
        self.file_path = file_path
        self.functions: List[FunctionInfo] = []
        self.modules: List[ModuleInfo] = []
        self.imports: List[ImportInfo] = []
        self.current_class: Optional[str] = None
        self.function_stack: List[str] = []

    def visit_Import(self, node: ast.Import):
        """处理 import 语句"""
        import_info = ImportInfo(
            module="",
            names=[alias.name for alias in node.names],
            line=node.lineno,
            is_from=False
        )
        self.imports.append(import_info)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """处理 from ... import 语句"""
        import_info = ImportInfo(
            module=node.module or "",
            names=[alias.name for alias in node.names],
            line=node.lineno,
            is_from=True
        )
        self.imports.append(import_info)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """处理函数定义"""
        self._process_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """处理异步函数定义"""
        self._process_function(node, is_async=False)

    def _process_function(self, node, is_async: bool):
        """处理函数节点"""
        func_name = node.name

        if func_name.startswith('_') and not func_name.startswith('__'):
            self.generic_visit(node)
            return

        params = [arg.arg for arg in node.args.args]

        returns = None
        if node.returns:
            returns = ast.unparse(node.returns)

        docstring = ast.get_docstring(node) or ""

        func_info = FunctionInfo(
            name=func_name,
            file=self.file_path,
            line=node.lineno,
            end_line=node.end_line or node.lineno,
            params=params,
            returns=returns,
            docstring=docstring,
            is_class_method=self.current_class is not None,
            class_name=self.current_class
        )

        self.function_stack.append(func_name)
        calls = self._extract_calls(node)
        func_info.calls = calls
        self.function_stack.pop()

        self.functions.append(func_info)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        """处理类定义"""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def _extract_calls(self, node: ast.AST) -> List[str]:
        """提取函数调用"""
        calls = []

        class CallVisitor(ast.NodeVisitor):
            def __init__(self):
                self.calls = []

            def visit_Call(self, call: ast.Call):
                if isinstance(call.func, ast.Name):
                    self.calls.append(call.func.id)
                elif isinstance(call.func, ast.Attribute):
                    name = call.func.attr
                    self.calls.append(name)

        visitor = CallVisitor()
        visitor.visit(node)
        calls = visitor.calls

        return list(set(calls))


def demo():
    """演示用法"""
    import json

    parser = PythonParser()
    parser.parse_directory("/path/to/project/backend")

    result = parser.get_call_graph_json()

    print("=" * 50)
    print(f"📊 解析结果统计")
    print(f"   函数数量: {result['statistics']['total_functions']}")
    print(f"   模块数量: {result['statistics']['total_modules']}")
    print(f"   调用关系: {result['statistics']['total_calls']}")
    print("=" * 50)

    print("\n📝 函数列表 (前 10 个):")
    for func in result['functions'][:10]:
        print(f"   {func['name']}({', '.join(func['params'])}) @ {func['file']}:{func['line']}")
        if func['calls']:
            print(f"      → 调用: {', '.join(func['calls'][:5])}")

    output_path = "/path/to/project/call_graph.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n✅ JSON 已保存到: {output_path}")


if __name__ == "__main__":
    demo()
