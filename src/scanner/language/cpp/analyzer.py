"""
C/C++ 代码分析器
使用正则表达式进行静态分析
"""
import re
import os
from typing import List, Optional
from scanner.language.base import BaseAnalyzer, FunctionInfo, ModuleInfo, ProjectInfo


class CppAnalyzer(BaseAnalyzer):
    """C/C++ 代码分析器"""

    SUPPORTED_EXTENSIONS = ['.c', '.cpp', '.h', '.hpp', '.cc', '.cxx', '.hxx']

    def __init__(self, root_path: str):
        super().__init__(root_path)

    @property
    def language_name(self) -> str:
        return "cpp"

    def is_supported_file(self, file_path: str) -> bool:
        return any(file_path.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS)

    def _preprocess(self, content: str) -> str:
        content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        content = re.sub(r'"[^"]*"', '""', content)
        return content

    def _extract_functions(self, content: str, file_path: str) -> List[FunctionInfo]:
        functions = []
        func_pattern = r'(?:template\s*<[^>]*>\s*)?((?:[\w_:\s\*&]+?)\s+)(\w+(?:::\w+)*)\s*\(([^)]*)\)\s*(?:const)?\s*(?:override)?\s*(?:noexcept)?\s*(?:->\s*[\w:&*]+\s*)?\{'

        for match in re.finditer(func_pattern, content, re.MULTILINE | re.DOTALL):
            return_type = match.group(1).strip()
            func_name = match.group(2).strip()
            params_str = match.group(3).strip()

            if func_name.startswith('~'):
                continue

            params = []
            if params_str:
                for param in params_str.split(','):
                    param = param.strip()
                    parts = param.split()
                    if parts:
                        param_name = parts[-1].replace('*', '').replace('&', '').strip()
                        if param_name and param_name not in ['void', '']:
                            params.append(param_name)

            is_method = '::' in func_name
            class_name = None
            if is_method:
                parts = func_name.split('::')
                func_name = parts[-1]
                class_name = '::'.join(parts[:-1])

            if return_type in ['template', '']:
                continue

            func_info = FunctionInfo(
                name=func_name,
                file_path=file_path,
                line_number=content[:match.start()].count('\n') + 1,
                parameters=params,
                return_type=return_type,
                is_method=is_method,
                class_name=class_name
            )

            func_body = self._get_function_body(content, match.end())
            func_info.calls = self._extract_calls(func_body)
            functions.append(func_info)

        return functions

    def _get_function_body(self, content: str, start_pos: int, max_depth: int = 10) -> str:
        depth = 0
        for i, char in enumerate(content[start_pos:], start_pos):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    return content[start_pos:i+1]
            if depth > max_depth:
                break
        return content[start_pos:start_pos+500]

    def _extract_calls(self, body: str) -> List[str]:
        calls = set()
        keywords = {'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'default',
                    'break', 'continue', 'return', 'goto', 'try', 'catch', 'throw',
                    'new', 'delete', 'sizeof', 'typedef', 'using', 'namespace',
                    'class', 'struct', 'enum', 'union', 'public', 'private', 'protected',
                    'virtual', 'override', 'final', 'const', 'static', 'inline', 'extern',
                    'void', 'int', 'float', 'double', 'char', 'bool', 'long', 'short',
                    'unsigned', 'signed', 'auto', 'nullptr', 'true', 'false', 'this',
                    'cout', 'cin', 'printf', 'scanf', 'malloc', 'free', 'calloc', 'realloc'}

        call_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*(?:::[a-zA-Z_][a-zA-Z0-9_]*)*)\s*\('
        for match in re.finditer(call_pattern, body):
            name = match.group(1)
            if name not in keywords and not name[0].isupper():
                calls.add(name)
        return list(calls)

    def _extract_includes(self, content: str) -> List[str]:
        includes = []
        for match in re.finditer(r'#include\s*[<"]([^>"]+)[>"]', content):
            includes.append(match.group(1))
        return includes

    def analyze_file(self, file_path: str) -> ModuleInfo:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        processed = self._preprocess(content)
        module_name = os.path.basename(file_path)
        module_info = ModuleInfo(
            name=module_name,
            file_path=file_path,
            line_number=1,
            imports=self._extract_includes(content)
        )
        module_info.functions.extend(self._extract_functions(processed, file_path))
        return module_info


def analyze_cpp_project(root_path: str) -> ProjectInfo:
    analyzer = CppAnalyzer(root_path)
    return analyzer.analyze()
