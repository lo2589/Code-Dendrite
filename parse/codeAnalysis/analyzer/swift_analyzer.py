"""
Swift 代码分析器
使用正则表达式进行静态分析
"""
import re
import os
from typing import List, Optional
from parse.codeAnalysis.analyzer.base import BaseAnalyzer, FunctionInfo, ModuleInfo, ProjectInfo


class SwiftAnalyzer(BaseAnalyzer):
    """Swift 代码分析器"""

    SUPPORTED_EXTENSIONS = ['.swift']

    def __init__(self, root_path: str):
        super().__init__(root_path)

    @property
    def language_name(self) -> str:
        return "swift"

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
        """提取 import 语句"""
        imports = []
        pattern = r'import\s+(\w+(?:\.\w+)*)'
        imports.extend(re.findall(pattern, source))
        return imports

    def _extract_classes(self, source: str) -> List[str]:
        """提取类、结构体、枚举、协议名"""
        items = []
        patterns = [
            r'(?:public\s+|private\s+|internal\s+|open\s+|final\s+)*class\s+(\w+)',
            r'(?:public\s+|private\s+|internal\s+)*struct\s+(\w+)',
            r'(?:public\s+|private\s+|internal\s+)*enum\s+(\w+)',
            r'(?:public\s+|private\s+|internal\s+)*protocol\s+(\w+)',
            r'(?:public\s+|private\s+|internal\s+)*extension\s+(\w+)',
        ]
        for pattern in patterns:
            items.extend(re.findall(pattern, source))
        return items

    def _extract_class_details(self, source: str, file_path: str) -> List[dict]:
        """提取类的详细信息"""
        classes = []
        class_pattern = r'(?:(?:public|private|internal|open|final)\s+)*(?:class|struct|enum)\s+(\w+)(?:\s*:\s*[\w,\s]+)?\s*\{'
        
        for match in re.finditer(class_pattern, source):
            class_name = match.group(1)
            class_start = match.start()
            class_body_start = match.end()
            
            # 找到匹配的 }
            class_body = self._get_block_body(source, class_body_start - 1)
            class_start_line = source[:class_start].count('\n') + 1
            
            methods = self._extract_methods(class_body, class_name, file_path, class_start_line)
            classes.append({
                'name': class_name,
                'methods': methods
            })
        
        return classes

    def _extract_methods(self, class_body: str, class_name: str, file_path: str, class_start_line: int) -> List[FunctionInfo]:
        """提取类方法"""
        methods = []
        # func 方法
        method_pattern = r'(?:(?:public|private|internal|open|override|static|class|final|mutating)\s+)*func\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)(?:\s*(?:throws\s+)?->\s*([^\{]+))?'
        
        for match in re.finditer(method_pattern, class_body):
            method_name = match.group(1)
            params_str = match.group(2) or ''
            return_type = match.group(3)
            
            params = self._parse_params(params_str)
            
            line_num = class_start_line + class_body[:match.start()].count('\n')
            
            func_info = FunctionInfo(
                name=method_name,
                file_path=file_path,
                line_number=line_num,
                parameters=params,
                return_type=return_type.strip() if return_type else None,
                is_method=True,
                class_name=class_name
            )
            
            # 提取方法体中的调用
            method_body = self._get_function_body(class_body, match.end())
            func_info.calls = self._extract_calls(method_body)
            
            methods.append(func_info)
        
        # init 构造器
        init_pattern = r'(?:(?:public|private|internal|convenience|required|override)\s+)*init\s*(?:\?)?\s*\(([^)]*)\)'
        for match in re.finditer(init_pattern, class_body):
            params_str = match.group(1) or ''
            params = self._parse_params(params_str)
            
            func_info = FunctionInfo(
                name='init',
                file_path=file_path,
                line_number=class_start_line + class_body[:match.start()].count('\n'),
                parameters=params,
                is_method=True,
                class_name=class_name
            )
            methods.append(func_info)
        
        return methods

    def _extract_functions(self, source: str, file_path: str) -> List[FunctionInfo]:
        """提取顶层函数"""
        functions = []
        preprocessed = self._preprocess(source)
        
        func_pattern = r'(?:(?:public|private|internal)\s+)?func\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)(?:\s*(?:throws\s+)?->\s*([^\{]+))?'
        
        for match in re.finditer(func_pattern, preprocessed):
            func_name = match.group(1)
            params_str = match.group(2) or ''
            return_type = match.group(3)
            
            # 检查是否在类/结构体内部
            before = preprocessed[:match.start()]
            type_count = len(re.findall(r'\b(?:class|struct|enum|extension)\s+\w+[^{]*\{', before))
            brace_balance = before.count('{') - before.count('}')
            
            if type_count > 0 and brace_balance > type_count - 1:
                continue
            
            params = self._parse_params(params_str)
            
            func_info = FunctionInfo(
                name=func_name,
                file_path=file_path,
                line_number=source[:match.start()].count('\n') + 1,
                parameters=params,
                return_type=return_type.strip() if return_type else None,
                is_method=False
            )
            
            func_body = self._get_function_body(preprocessed, match.end())
            func_info.calls = self._extract_calls(func_body)
            
            functions.append(func_info)
        
        return functions

    def _parse_params(self, params_str: str) -> List[str]:
        """解析参数列表"""
        params = []
        if not params_str.strip():
            return params
        
        # Swift 参数: externalName internalName: Type
        parts = params_str.split(',')
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # 取内部参数名
            if ':' in part:
                name_part = part.split(':')[0].strip()
                names = name_part.split()
                if len(names) >= 2:
                    params.append(names[1])  # 内部名
                elif len(names) == 1 and names[0] != '_':
                    params.append(names[0])
        
        return params

    def _get_function_body(self, content: str, start_pos: int) -> str:
        """获取函数体"""
        brace_start = content.find('{', start_pos)
        if brace_start == -1:
            return ""
        return self._get_block_body(content, brace_start)

    def _get_block_body(self, content: str, brace_pos: int) -> str:
        """获取大括号内的内容"""
        depth = 1
        i = brace_pos + 1
        while i < len(content) and depth > 0:
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
            i += 1
        return content[brace_pos + 1:i - 1]

    def _extract_calls(self, body: str) -> List[str]:
        """提取函数调用"""
        calls = set()
        # 函数调用
        pattern = r'(?<![.\w])(\w+)\s*\('
        for match in re.finditer(pattern, body):
            call_name = match.group(1)
            # 排除关键字
            if call_name not in ('if', 'while', 'for', 'switch', 'guard', 'func',
                                 'let', 'var', 'return', 'throw', 'catch', 'try',
                                 'class', 'struct', 'enum', 'protocol', 'extension',
                                 'init', 'deinit', 'case', 'default', 'where', 'as', 'is'):
                calls.add(call_name)
        
        # 方法调用
        method_pattern = r'\.(\w+)\s*\('
        for match in re.finditer(method_pattern, body):
            calls.add(match.group(1))
        
        # 类型方法调用 (如 ClassName.method())
        type_method_pattern = r'(\w+)\.(\w+)\s*\('
        for match in re.finditer(type_method_pattern, body):
            calls.add(f"{match.group(1)}.{match.group(2)}")
        
        return list(calls)
