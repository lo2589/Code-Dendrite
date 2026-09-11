"""
Go 代码分析器
使用正则表达式进行静态分析
"""
import re
import os
from typing import List, Optional
from parse.codeAnalysis.analyzer.base import BaseAnalyzer, FunctionInfo, ModuleInfo, ProjectInfo


class GoAnalyzer(BaseAnalyzer):
    """Go 代码分析器"""

    SUPPORTED_EXTENSIONS = ['.go']

    def __init__(self, root_path: str):
        super().__init__(root_path)

    @property
    def language_name(self) -> str:
        return "go"

    def is_supported_file(self, file_path: str) -> bool:
        return any(file_path.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS)

    def _preprocess(self, content: str) -> str:
        """移除注释"""
        # 移除单行注释
        content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
        # 移除多行注释
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        # 简化字符串
        content = re.sub(r'"[^"]*"', '""', content)
        content = re.sub(r'`[^`]*`', '``', content)
        return content

    def analyze_file(self, file_path: str) -> ModuleInfo:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()

        module_name = os.path.basename(file_path)
        module_info = ModuleInfo(name=module_name, file_path=file_path, line_number=1)

        module_info.imports = self._extract_imports(source)
        module_info.classes = self._extract_structs(source)
        
        # 提取函数和方法
        module_info.functions.extend(self._extract_functions(source, file_path))

        return module_info

    def _extract_imports(self, source: str) -> List[str]:
        """提取 import 语句"""
        imports = []
        # 单行 import
        pattern = r'import\s+"(.+?)"'
        imports.extend(re.findall(pattern, source))
        # 多行 import
        multi_pattern = r'import\s*\((.*?)\)'
        for match in re.finditer(multi_pattern, source, re.DOTALL):
            block = match.group(1)
            imports.extend(re.findall(r'"(.+?)"', block))
        return imports

    def _extract_structs(self, source: str) -> List[str]:
        """提取结构体名"""
        structs = []
        pattern = r'type\s+(\w+)\s+struct\s*\{'
        structs.extend(re.findall(pattern, source))
        # 接口
        pattern = r'type\s+(\w+)\s+interface\s*\{'
        structs.extend(re.findall(pattern, source))
        return structs

    def _extract_functions(self, source: str, file_path: str) -> List[FunctionInfo]:
        """提取函数和方法"""
        functions = []
        preprocessed = self._preprocess(source)
        
        # 函数模式: func name(params) returns
        # 方法模式: func (receiver) name(params) returns
        func_pattern = r'func\s+(?:\((\w+)\s+\*?(\w+)\)\s+)?(\w+)\s*\(([^)]*)\)(?:\s*(?:\(([^)]*)\)|(\w+)))?'
        
        for match in re.finditer(func_pattern, preprocessed):
            receiver_name = match.group(1)
            receiver_type = match.group(2)
            func_name = match.group(3)
            params_str = match.group(4) or ''
            returns_multi = match.group(5)
            returns_single = match.group(6)
            
            # 解析参数
            params = self._parse_params(params_str)
            
            # 解析返回类型
            return_type = None
            if returns_multi:
                return_type = f"({returns_multi})"
            elif returns_single:
                return_type = returns_single
            
            is_method = receiver_type is not None
            class_name = receiver_type if is_method else None
            
            func_info = FunctionInfo(
                name=func_name,
                file_path=file_path,
                line_number=source[:match.start()].count('\n') + 1,
                parameters=params,
                return_type=return_type,
                is_method=is_method,
                class_name=class_name
            )
            
            # 提取函数体中的调用
            func_body = self._get_function_body(preprocessed, match.end())
            func_info.calls = self._extract_calls(func_body)
            
            functions.append(func_info)
        
        return functions

    def _parse_params(self, params_str: str) -> List[str]:
        """解析参数列表"""
        params = []
        if not params_str.strip():
            return params
        
        # Go 的参数可能是 "a, b int" 或 "a int, b string"
        parts = params_str.split(',')
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # 取第一个词作为参数名
            words = part.split()
            if words:
                param_name = words[0]
                if param_name not in ('func', 'map', 'chan', 'interface', 'struct'):
                    params.append(param_name)
        
        return params

    def _get_function_body(self, content: str, start_pos: int) -> str:
        """获取函数体"""
        # 找到开始的 {
        brace_start = content.find('{', start_pos)
        if brace_start == -1:
            return ""
        
        depth = 1
        i = brace_start + 1
        while i < len(content) and depth > 0:
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
            i += 1
        
        return content[brace_start + 1:i - 1]

    def _extract_calls(self, body: str) -> List[str]:
        """提取函数调用"""
        calls = set()
        # 函数调用
        pattern = r'(?<![.\w])(\w+)\s*\('
        for match in re.finditer(pattern, body):
            call_name = match.group(1)
            # 排除关键字
            if call_name not in ('if', 'for', 'switch', 'select', 'case', 'func',
                                 'go', 'defer', 'return', 'make', 'new', 'len',
                                 'cap', 'append', 'copy', 'delete', 'close',
                                 'panic', 'recover', 'print', 'println', 'range'):
                calls.add(call_name)
        
        # 方法调用
        method_pattern = r'\.(\w+)\s*\('
        for match in re.finditer(method_pattern, body):
            calls.add(match.group(1))
        
        # 包函数调用
        pkg_pattern = r'(\w+)\.(\w+)\s*\('
        for match in re.finditer(pkg_pattern, body):
            calls.add(f"{match.group(1)}.{match.group(2)}")
        
        return list(calls)
