"""
Python 代码分析器
使用 Python AST 模块进行静态分析
"""
import ast
import os
from typing import List, Set, Optional
from .base import BaseAnalyzer, FunctionInfo, ModuleInfo, ProjectInfo


class PythonAnalyzer(BaseAnalyzer):
    """Python 代码分析器"""

    SUPPORTED_EXTENSIONS = ['.py']

    def __init__(self, root_path: str):
        super().__init__(root_path)
        self.current_class_stack: List[str] = []

    @property
    def language_name(self) -> str:
        return "python"

    def is_supported_file(self, file_path: str) -> bool:
        return any(file_path.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS)

    def analyze_file(self, file_path: str) -> ModuleInfo:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()

        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            print(f"语法错误 {file_path}: {e}")
            return ModuleInfo(name=os.path.basename(file_path), file_path=file_path, line_number=1)

        module_name = os.path.basename(file_path)
        if module_name.endswith('.py'):
            module_name = module_name[:-3]

        module_info = ModuleInfo(name=module_name, file_path=file_path, line_number=1)

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                self._process_class(node, module_info, file_path)
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                self._process_function(node, module_info, file_path)
            elif isinstance(node, ast.Import):
                module_info.imports.extend([alias.name for alias in node.names])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_info.imports.append(node.module)

        return module_info

    def _process_class(self, node: ast.ClassDef, module_info: ModuleInfo, file_path: str):
        class_name = node.name
        module_info.classes.append(class_name)
        self.current_class_stack.append(class_name)

        for item in node.body:
            if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                self._process_function(item, module_info, file_path)

        for item in node.body:
            if isinstance(item, ast.ClassDef):
                self._process_class(item, module_info, file_path)

        self.current_class_stack.pop()

    def _process_function(self, node, module_info: ModuleInfo, file_path: str):
        func_info = FunctionInfo(
            name=node.name,
            file_path=file_path,
            line_number=node.lineno,
            is_async=isinstance(node, ast.AsyncFunctionDef)
        )

        func_info.parameters = [arg.arg for arg in node.args.args]

        try:
            func_info.decorators = [ast.unparse(d) for d in node.decorator_list]
        except:
            func_info.decorators = [str(d) for d in node.decorator_list]

        func_info.docstring = ast.get_docstring(node)

        if self.current_class_stack:
            func_info.is_method = True
            func_info.class_name = self.current_class_stack[-1]

        func_info.calls = self._extract_calls(node)
        module_info.functions.append(func_info)

    def _extract_calls(self, node) -> List[str]:
        calls = []
        depth = 0

        for child in ast.walk(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                depth += 1
                continue
            if isinstance(child, ast.Call) and depth == 1:
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)

        return list(set(calls))


def analyze_python_project(root_path: str) -> ProjectInfo:
    analyzer = PythonAnalyzer(root_path)
    return analyzer.analyze()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python python_analyzer.py <项目路径>")
        sys.exit(1)
    project_info = analyze_python_project(sys.argv[1])
    print(f"项目: {sys.argv[1]}")
    print(f"文件数: {len(project_info.files)}, 函数数: {len(project_info.functions)}")
