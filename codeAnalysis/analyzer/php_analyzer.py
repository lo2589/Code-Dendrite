"""
PHP 代码分析器
使用正则表达式进行静态分析
"""
import re
import os
from typing import List, Optional
from .base import BaseAnalyzer, FunctionInfo, ModuleInfo, ProjectInfo


class PhpAnalyzer(BaseAnalyzer):
    """PHP 代码分析器"""

    SUPPORTED_EXTENSIONS = ['.php', '.phtml', '.php5', '.php7']

    def __init__(self, root_path: str):
        super().__init__(root_path)
        self.current_class: Optional[str] = None

    @property
    def language_name(self) -> str:
        return "php"

    def is_supported_file(self, file_path: str) -> bool:
        return any(file_path.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS)

    def _preprocess(self, content: str) -> str:
        """移除注释和字符串"""
        # 移除单行注释
        content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
        content = re.sub(r'#.*?$', '', content, flags=re.MULTILINE)
        # 移除多行注释
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        # 简化字符串
        content = re.sub(r'"[^"]*"', '""', content)
        content = re.sub(r"'[^']*'", "''", content)
        return content

    def analyze_file(self, file_path: str) -> ModuleInfo:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()

        module_name = os.path.basename(file_path)
        module_info = ModuleInfo(name=module_name, file_path=file_path, line_number=1)

        module_info.imports = self._extract_imports(source)
        module_info.classes = self._extract_classes(source)
        
        # 提取类方法
        for cls_info in self._extract_class_details(source, file_path):
            module_info.functions.extend(cls_info['methods'])
        
        # 提取顶层函数
        module_info.functions.extend(self._extract_functions(source, file_path))

        return module_info

    def _extract_imports(self, source: str) -> List[str]:
        """提取 use/require/include 语句"""
        imports = []
        patterns = [
            r'use\s+([\w\\]+)',
            r'require(?:_once)?\s*\(?[\'"](.+?)[\'"]\)?',
            r'include(?:_once)?\s*\(?[\'"](.+?)[\'"]\)?',
        ]
        for pattern in patterns:
            imports.extend(re.findall(pattern, source))
        return imports

    def _extract_classes(self, source: str) -> List[str]:
        """提取类名"""
        classes = []
        pattern = r'(?:abstract\s+)?class\s+(\w+)'
        classes.extend(re.findall(pattern, source))
        # 接口和 trait
        pattern = r'(?:interface|trait)\s+(\w+)'
        classes.extend(re.findall(pattern, source))
        return classes

    def _extract_class_details(self, source: str, file_path: str) -> List[dict]:
        """提取类的详细信息"""
        classes = []
        class_pattern = r'(?:(?:abstract|final)?\s*)?class\s+(\w+)(?:\s+extends\s+\w+)?(?:\s+implements\s+[\w,\s]+)?\s*\{'
        
        for match in re.finditer(class_pattern, source):
            class_name = match.group(1)
            start_pos = match.start()
            end_pos = self._find_matching_brace(source, match.end() - 1)
            class_body = source[match.end():end_pos]
            
            methods = self._extract_methods(class_body, class_name, file_path, 
                                           source[:start_pos].count('\n') + 1)
            classes.append({
                'name': class_name,
                'methods': methods
            })
        
        return classes

    def _find_matching_brace(self, content: str, start: int) -> int:
        """找到匹配的大括号"""
        depth = 1
        i = start + 1
        while i < len(content) and depth > 0:
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
            i += 1
        return i

    def _extract_methods(self, class_body: str, class_name: str, file_path: str, class_start_line: int) -> List[FunctionInfo]:
        """提取类方法"""
        methods = []
        method_pattern = r'(?:(?:public|private|protected|static|final|abstract)?\s+)*function\s+(\w+)\s*\(([^)]*)\)'
        
        for match in re.finditer(method_pattern, class_body):
            method_name = match.group(1)
            params_str = match.group(2).strip()
            
            params = []
            if params_str:
                for param in params_str.split(','):
                    param = param.strip()
                    # 处理类型提示和默认值
                    param_match = re.search(r'\$(\w+)', param)
                    if param_match:
                        params.append(param_match.group(1))
            
            line_num = class_start_line + class_body[:match.start()].count('\n')
            
            func_info = FunctionInfo(
                name=method_name,
                file_path=file_path,
                line_number=line_num,
                parameters=params,
                is_method=True,
                class_name=class_name
            )
            
            # 提取方法体中的调用
            method_end = self._find_matching_brace(class_body, match.end())
            method_body = class_body[match.end():method_end]
            func_info.calls = self._extract_calls(method_body)
            
            methods.append(func_info)
        
        return methods

    def _extract_functions(self, source: str, file_path: str) -> List[FunctionInfo]:
        """提取顶层函数"""
        functions = []
        preprocessed = self._preprocess(source)
        
        # 排除类中的函数
        func_pattern = r'(?<![\w])function\s+(\w+)\s*\(([^)]*)\)'
        
        for match in re.finditer(func_pattern, preprocessed):
            func_name = match.group(1)
            params_str = match.group(2).strip()
            
            # 检查是否在类内部
            before = preprocessed[:match.start()]
            if 'class ' in before:
                # 简单检查是否在类定义内
                last_class = before.rfind('class ')
                if before[last_class:].count('{') > before[last_class:].count('}'):
                    continue
            
            params = []
            if params_str:
                for param in params_str.split(','):
                    param_match = re.search(r'\$(\w+)', param)
                    if param_match:
                        params.append(param_match.group(1))
            
            func_info = FunctionInfo(
                name=func_name,
                file_path=file_path,
                line_number=source[:match.start()].count('\n') + 1,
                parameters=params,
                is_method=False
            )
            
            functions.append(func_info)
        
        return functions

    def _extract_calls(self, body: str) -> List[str]:
        """提取函数调用"""
        calls = set()
        # 普通函数调用
        pattern = r'(\w+)\s*\('
        for match in re.finditer(pattern, body):
            call_name = match.group(1)
            # 排除关键字
            if call_name not in ('if', 'while', 'for', 'foreach', 'switch', 'catch', 
                                 'function', 'class', 'array', 'isset', 'empty', 'unset',
                                 'echo', 'print', 'return', 'new'):
                calls.add(call_name)
        
        # 方法调用
        method_pattern = r'(?:\$\w+|self|static|parent)->(\w+)\s*\('
        for match in re.finditer(method_pattern, body):
            calls.add(match.group(1))
        
        # 静态方法调用
        static_pattern = r'(\w+)::(\w+)\s*\('
        for match in re.finditer(static_pattern, body):
            calls.add(f"{match.group(1)}::{match.group(2)}")
        
        return list(calls)
