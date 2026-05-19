"""
Ruby 代码分析器
使用正则表达式进行静态分析
"""
import re
import os
from typing import List, Optional
from .base import BaseAnalyzer, FunctionInfo, ModuleInfo, ProjectInfo


class RubyAnalyzer(BaseAnalyzer):
    """Ruby 代码分析器"""

    SUPPORTED_EXTENSIONS = ['.rb', '.rake', '.gemspec']

    def __init__(self, root_path: str):
        super().__init__(root_path)
        self.current_class: Optional[str] = None

    @property
    def language_name(self) -> str:
        return "ruby"

    def is_supported_file(self, file_path: str) -> bool:
        return any(file_path.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS)

    def _preprocess(self, content: str) -> str:
        """移除注释"""
        # 移除单行注释
        content = re.sub(r'#.*?$', '', content, flags=re.MULTILINE)
        # 移除多行注释 =begin ... =end
        content = re.sub(r'=begin.*?=end', '', content, flags=re.DOTALL)
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
        
        # 提取顶层方法
        module_info.functions.extend(self._extract_functions(source, file_path))

        return module_info

    def _extract_imports(self, source: str) -> List[str]:
        """提取 require 语句"""
        imports = []
        patterns = [
            r"require\s+['\"](.+?)['\"]",
            r"require_relative\s+['\"](.+?)['\"]",
            r"load\s+['\"](.+?)['\"]",
            r"include\s+(\w+)",
            r"extend\s+(\w+)",
        ]
        for pattern in patterns:
            imports.extend(re.findall(pattern, source))
        return imports

    def _extract_classes(self, source: str) -> List[str]:
        """提取类名"""
        classes = []
        pattern = r'class\s+(\w+)'
        classes.extend(re.findall(pattern, source))
        # 模块
        pattern = r'module\s+(\w+)'
        classes.extend(re.findall(pattern, source))
        return classes

    def _extract_class_details(self, source: str, file_path: str) -> List[dict]:
        """提取类的详细信息"""
        classes = []
        class_pattern = r'class\s+(\w+)(?:\s*<\s*[\w:]+)?\s*$'
        
        lines = source.split('\n')
        i = 0
        while i < len(lines):
            match = re.match(class_pattern, lines[i].strip())
            if match:
                class_name = match.group(1)
                class_start = i
                
                # 找到 end
                depth = 1
                j = i + 1
                while j < len(lines) and depth > 0:
                    line = lines[j].strip()
                    if re.match(r'^(class|module|def|if|unless|while|until|for|case|begin|do)\b', line):
                        depth += 1
                    elif line == 'end':
                        depth -= 1
                    j += 1
                
                class_body = '\n'.join(lines[i+1:j-1])
                methods = self._extract_methods(class_body, class_name, file_path, class_start + 1)
                classes.append({
                    'name': class_name,
                    'methods': methods
                })
                i = j
            else:
                i += 1
        
        return classes

    def _extract_methods(self, class_body: str, class_name: str, file_path: str, class_start_line: int) -> List[FunctionInfo]:
        """提取类方法"""
        methods = []
        method_pattern = r'def\s+(self\.)?(\w+[?!=]?)\s*(?:\(([^)]*)\))?'
        
        for match in re.finditer(method_pattern, class_body):
            is_class_method = match.group(1) is not None
            method_name = match.group(2)
            params_str = match.group(3) or ''
            
            params = []
            if params_str:
                for param in params_str.split(','):
                    param = param.strip()
                    # 移除默认值
                    param = param.split('=')[0].strip()
                    # 移除 * 和 ** 前缀
                    param = param.lstrip('*&')
                    if param and not param.startswith(':'):
                        params.append(param)
            
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
            method_body = self._extract_method_body(class_body, match.end())
            func_info.calls = self._extract_calls(method_body)
            
            methods.append(func_info)
        
        return methods

    def _extract_method_body(self, content: str, start: int) -> str:
        """提取方法体"""
        lines = content[start:].split('\n')
        depth = 1
        end_line = 0
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r'^(def|class|module|if|unless|while|until|for|case|begin|do)\b', stripped):
                depth += 1
            elif stripped == 'end':
                depth -= 1
                if depth == 0:
                    end_line = i
                    break
        
        return '\n'.join(lines[:end_line])

    def _extract_functions(self, source: str, file_path: str) -> List[FunctionInfo]:
        """提取顶层方法"""
        functions = []
        preprocessed = self._preprocess(source)
        
        method_pattern = r'^def\s+(\w+[?!=]?)\s*(?:\(([^)]*)\))?'
        
        for match in re.finditer(method_pattern, preprocessed, re.MULTILINE):
            method_name = match.group(1)
            params_str = match.group(2) or ''
            
            # 检查是否在类/模块内部
            before = preprocessed[:match.start()]
            class_count = len(re.findall(r'^class\s', before, re.MULTILINE))
            module_count = len(re.findall(r'^module\s', before, re.MULTILINE))
            end_count = len(re.findall(r'^end\s*$', before, re.MULTILINE))
            
            if class_count + module_count > end_count:
                continue
            
            params = []
            if params_str:
                for param in params_str.split(','):
                    param = param.strip().split('=')[0].strip().lstrip('*&')
                    if param and not param.startswith(':'):
                        params.append(param)
            
            func_info = FunctionInfo(
                name=method_name,
                file_path=file_path,
                line_number=source[:match.start()].count('\n') + 1,
                parameters=params,
                is_method=False
            )
            
            functions.append(func_info)
        
        return functions

    def _extract_calls(self, body: str) -> List[str]:
        """提取方法调用"""
        calls = set()
        # 方法调用
        pattern = r'(?<![.\w])(\w+[?!]?)\s*(?:\(|$)'
        for match in re.finditer(pattern, body):
            call_name = match.group(1)
            # 排除关键字
            if call_name not in ('if', 'unless', 'while', 'until', 'for', 'case', 
                                 'when', 'def', 'class', 'module', 'begin', 'end',
                                 'do', 'return', 'yield', 'raise', 'rescue', 'ensure',
                                 'nil', 'true', 'false', 'and', 'or', 'not'):
                calls.add(call_name)
        
        # 对象方法调用
        method_pattern = r'\.(\w+[?!]?)\s*(?:\(|$)'
        for match in re.finditer(method_pattern, body):
            calls.add(match.group(1))
        
        return list(calls)
