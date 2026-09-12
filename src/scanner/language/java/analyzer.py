"""
Java 代码分析器
使用正则表达式进行静态分析
"""
import re
import os
from typing import List, Optional
from scanner.language.base import BaseAnalyzer, FunctionInfo, ModuleInfo, ProjectInfo


class JavaAnalyzer(BaseAnalyzer):
    """Java 代码分析器"""

    SUPPORTED_EXTENSIONS = ['.java']

    def __init__(self, root_path: str):
        super().__init__(root_path)
        self.current_class: Optional[str] = None

    @property
    def language_name(self) -> str:
        return "java"

    def is_supported_file(self, file_path: str) -> bool:
        return any(file_path.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS)

    def _preprocess(self, content: str) -> str:
        content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        content = re.sub(r'"[^"]*"', '""', content)
        return content

    def _extract_classes(self, content: str, file_path: str) -> List[dict]:
        classes = []
        class_pattern = r'(?:(?:public|private|protected|static|final|abstract)?\s+)*class\s+(\w+)'
        for match in re.finditer(class_pattern, content):
            class_name = match.group(1)
            start_pos = match.start()
            end_pos = self._find_matching_brace(content, start_pos)
            class_body = content[start_pos:end_pos]
            classes.append({
                'name': class_name,
                'body': class_body,
                'start_line': content[:start_pos].count('\n') + 1
            })
        return classes

    def _find_matching_brace(self, content: str, start: int) -> int:
        depth = 0
        in_string = False
        in_char = False
        i = start
        while i < len(content):
            char = content[i]
            if char == '"' and not in_char:
                in_string = not in_string
            elif char == "'" and not in_string:
                in_char = not in_char
            elif not in_string and not in_char:
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        return i + 1
            i += 1
        return len(content)

    def _extract_methods(self, class_body: str, class_name: str, file_path: str, class_start_line: int) -> List[FunctionInfo]:
        methods = []
        method_pattern = r'(?:(?:public|private|protected|static|final|abstract|synchronized)?\s+)*((?:[\w<>,\s?]+?)\s+)(\w+)\s*\(([^)]*)\)\s*(?:throws\s+[\w,\s]+)?\s*\{'

        for match in re.finditer(method_pattern, class_body, re.DOTALL):
            return_type = match.group(1).strip()
            method_name = match.group(2).strip()
            params_str = match.group(3).strip()

            if method_name == class_name:
                continue

            params = []
            if params_str:
                for param in params_str.split(','):
                    param = param.strip()
                    parts = param.split()
                    if parts:
                        param_name = parts[-1].replace('*', '').strip()
                        if param_name and param_name not in ['void', '']:
                            params.append(param_name)

            if return_type in ['class', 'interface', 'enum']:
                continue

            func_info = FunctionInfo(
                name=method_name,
                file_path=file_path,
                line_number=class_start_line + class_body[:match.start()].count('\n'),
                parameters=params,
                return_type=return_type,
                is_method=True,
                class_name=class_name
            )

            body_start = match.start() + class_body[match.start():].find('{')
            func_info.calls = self._extract_calls(class_body[body_start:body_start+500] if len(class_body) > body_start else class_body[body_start:])
            methods.append(func_info)

        return methods

    def _extract_calls(self, body: str) -> List[str]:
        calls = set()
        keywords = {'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'default',
                    'break', 'continue', 'return', 'new', 'this', 'super',
                    'try', 'catch', 'finally', 'throw', 'throws',
                    'public', 'private', 'protected', 'static', 'final', 'abstract',
                    'class', 'interface', 'extends', 'implements', 'package', 'import',
                    'void', 'int', 'float', 'double', 'char', 'boolean', 'byte', 'short', 'long',
                    'true', 'false', 'null', 'instanceof', 'synchronized',
                    'System', 'out', 'println', 'printf', 'print',
                    'String', 'Integer', 'Boolean', 'Double', 'Float', 'Long', 'Short', 'Byte',
                    'Object', 'Class', 'Thread', 'Runnable', 'Exception', 'Error', 'Throwable'}

        call_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        for match in re.finditer(call_pattern, body):
            name = match.group(1)
            if name not in keywords:
                calls.add(name)
        return list(calls)

    def _extract_imports(self, content: str) -> List[str]:
        imports = []
        for match in re.finditer(r'import\s+([\w.]+);', content):
            imports.append(match.group(1))
        return imports

    def analyze_file(self, file_path: str) -> ModuleInfo:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        processed = self._preprocess(content)
        module_name = os.path.basename(file_path)
        if module_name.endswith('.java'):
            module_name = module_name[:-5]
        module_info = ModuleInfo(
            name=module_name,
            file_path=file_path,
            line_number=1,
            imports=self._extract_imports(content)
        )
        classes = self._extract_classes(processed, file_path)
        for cls in classes:
            methods = self._extract_methods(cls['body'], cls['name'], file_path, cls['start_line'])
            module_info.functions.extend(methods)
            module_info.classes.append(cls['name'])
        return module_info


def analyze_java_project(root_path: str) -> ProjectInfo:
    analyzer = JavaAnalyzer(root_path)
    return analyzer.analyze()
