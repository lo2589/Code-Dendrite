"""
TypeScript/JavaScript 代码分析器
增强版：支持 UI 事件提取和数据流分析
"""
import os
import re
from typing import List, Set, Optional, Dict
from .base import BaseAnalyzer, FunctionInfo, ModuleInfo, ProjectInfo


class TypeScriptAnalyzer(BaseAnalyzer):
    """TypeScript/JavaScript 代码分析器"""

    SUPPORTED_EXTENSIONS = ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs']

    def __init__(self, root_path: str):
        super().__init__(root_path)
        self.ui_events: List[Dict] = []
        self.message_commands: Dict[str, int] = {}

    @property
    def language_name(self) -> str:
        return "typescript"

    def is_supported_file(self, file_path: str) -> bool:
        return any(file_path.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS)

    def analyze_file(self, file_path: str) -> ModuleInfo:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()

        module_name = os.path.basename(file_path)
        module_info = ModuleInfo(name=module_name, file_path=file_path, line_number=1)

        module_info.imports = self._extract_imports(source)
        module_info.classes = self._extract_classes(source)
        functions = self._extract_functions(source, file_path)
        module_info.functions.extend(functions)

        self._extract_ui_events(source, file_path)
        self._extract_postmessage_commands(source)

        return module_info

    def _extract_imports(self, source: str) -> List[str]:
        imports = []
        patterns = [
            r'import\s+.*?from\s+[\'"](.+?)[\'"]',
            r'import\s+[\'"](.+?)[\'"]',
            r'require\([\'"](.+?)[\'"]\)',
        ]
        for pattern in patterns:
            imports.extend(re.findall(pattern, source))
        return imports

    def _extract_classes(self, source: str) -> List[str]:
        classes = []
        pattern = r'class\s+(\w+)'
        classes.extend(re.findall(pattern, source))
        pattern = r'(\w+)\s*=\s*class'
        classes.extend(re.findall(pattern, source))
        return classes

    def _extract_ui_events(self, source: str, file_path: str):
        inline_pattern = r'(onclick|onchange|onsubmit|oninput|onkeydown|onkeyup|onfocus|onblur)\s*=\s*["\']?([^"\';\s]+)["\']?'
        for match in re.finditer(inline_pattern, source):
            event_type = match.group(1)
            handler = match.group(2).replace('()', '')
            line_num = source[:match.start()].count('\n') + 1
            self.ui_events.append({
                'event': event_type,
                'handler': handler,
                'file': file_path,
                'line': line_num,
                'type': 'inline'
            })

        add_event_pattern = r'(?:getElementById|querySelector)[^;]*?\.addEventListener\([\'"]([\w]+)[\'"]\s*,\s*(\w+)'
        for match in re.finditer(add_event_pattern, source):
            event_type = match.group(1)
            handler = match.group(2)
            line_num = source[:match.start()].count('\n') + 1
            self.ui_events.append({
                'event': event_type,
                'handler': handler,
                'file': file_path,
                'line': line_num,
                'type': 'addEventListener'
            })

    def _extract_postmessage_commands(self, source: str):
        pattern = r'vscode\.postMessage\s*\(\s*\{[^}]*command\s*:\s*[\'"]?(\w+)'
        for match in re.finditer(pattern, source):
            cmd = match.group(1)
            self.message_commands[cmd] = self.message_commands.get(cmd, 0) + 1

    def _extract_functions(self, source: str, file_path: str) -> List[FunctionInfo]:
        functions = []

        function_patterns = [
            (r'(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)', 'function'),
            (r'const\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>', 'arrow'),
            (r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?function', 'function_expr'),
        ]

        class_matches = list(re.finditer(r'class\s+(\w+)', source))
        current_class = None
        for i, match in enumerate(class_matches):
            if i == 0:
                current_class = match.group(1)
            else:
                break

        for pattern, func_type in function_patterns:
            for match in re.finditer(pattern, source):
                func_name = match.group(1)
                params = match.group(2) if match.group(2) else ''
                line_num = source[:match.start()].count('\n') + 1

                param_list = [p.strip().split(':')[0].strip() for p in params.split(',') if p.strip()]

                is_method = current_class is not None and func_type != 'function'

                func_info = FunctionInfo(
                    name=func_name,
                    file_path=file_path,
                    line_number=line_num,
                    parameters=param_list,
                    is_method=is_method,
                    class_name=current_class
                )

                func_body = self._extract_function_body(source, match.end())
                func_info.calls = self._extract_calls(func_body)

                functions.append(func_info)

        method_pattern = r'(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*(?::\s*[\w<>[\],\s]|=>)?\s*\{'
        for match in re.finditer(method_pattern, source):
            func_name = match.group(1)
            params = match.group(2) if match.group(2) else ''
            if func_name in ['if', 'for', 'while', 'switch', 'catch', 'class', 'function', 'constructor']:
                continue
            if '=>' in source[match.start():match.end()]:
                continue

            line_num = source[:match.start()].count('\n') + 1
            param_list = [p.strip().split(':')[0].strip() for p in params.split(',') if p.strip()]

            func_body = self._extract_function_body(source, match.end())
            calls = self._extract_calls(func_body)

            func_info = FunctionInfo(
                name=func_name,
                file_path=file_path,
                line_number=line_num,
                parameters=param_list,
                is_method=current_class is not None,
                class_name=current_class,
                calls=calls
            )
            functions.append(func_info)

        return functions

    def _extract_function_body(self, source: str, start: int) -> str:
        if start >= len(source) or source[start] != '{':
            return ''

        brace_count = 0
        started = False
        end = start

        for i in range(start, len(source)):
            char = source[i]
            if char == '{':
                brace_count += 1
                started = True
            elif char == '}':
                brace_count -= 1
                if started and brace_count == 0:
                    end = i + 1
                    break

        return source[start:end]

    def _extract_calls(self, body: str) -> List[str]:
        calls = []

        exclude_list = [
            'if', 'for', 'while', 'switch', 'catch', 'return', 'throw',
            'new', 'typeof', 'instanceof', 'delete', 'void', 'await',
            'else', 'case', 'default', 'break', 'continue', 'yield',
            'var', 'let', 'const', 'class', 'function', 'import', 'export'
        ]

        call_pattern = r'(?:^|[^.\w])(\w+)\s*\('
        matches = re.findall(call_pattern, body)
        for call in matches:
            if call not in exclude_list and not call[0].isupper():
                calls.append(call)

        method_pattern = r'(?:this|self|super|\w+)\.(\w+)\s*\('
        method_calls = re.findall(method_pattern, body)
        for call in method_calls:
            if call not in exclude_list:
                calls.append(call)

        return list(set(calls))

    def analyze(self) -> ProjectInfo:
        project_info = super().analyze()
        project_info.ui_events = self.ui_events
        project_info.message_commands = self.message_commands
        return project_info


def analyze_typescript_project(root_path: str) -> ProjectInfo:
    analyzer = TypeScriptAnalyzer(root_path)
    return analyzer.analyze()
