"""
Rust 代码分析器
使用正则表达式进行静态分析
"""
import re
import os
from typing import List, Optional
from .base import BaseAnalyzer, FunctionInfo, ModuleInfo, ProjectInfo


class RustAnalyzer(BaseAnalyzer):
    """Rust 代码分析器"""

    SUPPORTED_EXTENSIONS = ['.rs']

    def __init__(self, root_path: str):
        super().__init__(root_path)

    @property
    def language_name(self) -> str:
        return "rust"

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
        module_info.classes = self._extract_structs(source)
        
        # 提取函数和方法
        module_info.functions.extend(self._extract_functions(source, file_path))
        # 提取 impl 块中的方法
        module_info.functions.extend(self._extract_impl_methods(source, file_path))

        return module_info

    def _extract_imports(self, source: str) -> List[str]:
        """提取 use 语句"""
        imports = []
        # use 语句
        pattern = r'use\s+([\w:]+(?:::\{[^}]+\})?)'
        imports.extend(re.findall(pattern, source))
        # extern crate
        pattern = r'extern\s+crate\s+(\w+)'
        imports.extend(re.findall(pattern, source))
        # mod 语句
        pattern = r'mod\s+(\w+)'
        imports.extend(re.findall(pattern, source))
        return imports

    def _extract_structs(self, source: str) -> List[str]:
        """提取结构体和枚举名"""
        items = []
        # struct
        pattern = r'(?:pub\s+)?struct\s+(\w+)'
        items.extend(re.findall(pattern, source))
        # enum
        pattern = r'(?:pub\s+)?enum\s+(\w+)'
        items.extend(re.findall(pattern, source))
        # trait
        pattern = r'(?:pub\s+)?trait\s+(\w+)'
        items.extend(re.findall(pattern, source))
        return items

    def _extract_functions(self, source: str, file_path: str) -> List[FunctionInfo]:
        """提取顶层函数"""
        functions = []
        preprocessed = self._preprocess(source)
        
        # 函数模式: fn name<generics>(params) -> return
        func_pattern = r'(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)(?:\s*->\s*([^\{]+))?'
        
        for match in re.finditer(func_pattern, preprocessed):
            func_name = match.group(1)
            params_str = match.group(2) or ''
            return_type = match.group(3)
            
            # 检查是否在 impl 块内
            before = preprocessed[:match.start()]
            impl_count = len(re.findall(r'\bimpl\b', before))
            brace_balance = before.count('{') - before.count('}')
            
            # 如果在 impl 块内，跳过（由 _extract_impl_methods 处理）
            if impl_count > 0 and brace_balance > 0:
                continue
            
            # 解析参数
            params = self._parse_params(params_str)
            
            func_info = FunctionInfo(
                name=func_name,
                file_path=file_path,
                line_number=source[:match.start()].count('\n') + 1,
                parameters=params,
                return_type=return_type.strip() if return_type else None,
                is_async='async' in preprocessed[max(0, match.start()-10):match.start()],
                is_method=False
            )
            
            # 提取函数体中的调用
            func_body = self._get_function_body(preprocessed, match.end())
            func_info.calls = self._extract_calls(func_body)
            
            functions.append(func_info)
        
        return functions

    def _extract_impl_methods(self, source: str, file_path: str) -> List[FunctionInfo]:
        """提取 impl 块中的方法"""
        methods = []
        preprocessed = self._preprocess(source)
        
        # impl 块模式
        impl_pattern = r'impl(?:\s*<[^>]*>)?\s+(?:(\w+)\s+for\s+)?(\w+)(?:\s*<[^>]*>)?\s*\{'
        
        for impl_match in re.finditer(impl_pattern, preprocessed):
            trait_name = impl_match.group(1)
            struct_name = impl_match.group(2)
            impl_start = impl_match.end()
            
            # 找到 impl 块结束
            impl_body = self._get_block_body(preprocessed, impl_start - 1)
            impl_start_line = source[:impl_match.start()].count('\n') + 1
            
            # 在 impl 块内查找方法
            method_pattern = r'(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)(?:\s*->\s*([^\{]+))?'
            
            for method_match in re.finditer(method_pattern, impl_body):
                method_name = method_match.group(1)
                params_str = method_match.group(2) or ''
                return_type = method_match.group(3)
                
                params = self._parse_params(params_str)
                is_self_method = 'self' in params_str.split(',')[0] if params_str else False
                
                func_info = FunctionInfo(
                    name=method_name,
                    file_path=file_path,
                    line_number=impl_start_line + impl_body[:method_match.start()].count('\n'),
                    parameters=params,
                    return_type=return_type.strip() if return_type else None,
                    is_async='async' in impl_body[max(0, method_match.start()-10):method_match.start()],
                    is_method=is_self_method,
                    class_name=struct_name
                )
                
                method_body = self._get_function_body(impl_body, method_match.end())
                func_info.calls = self._extract_calls(method_body)
                
                methods.append(func_info)
        
        return methods

    def _parse_params(self, params_str: str) -> List[str]:
        """解析参数列表"""
        params = []
        if not params_str.strip():
            return params
        
        parts = params_str.split(',')
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # 跳过 self 参数
            if part in ('self', '&self', '&mut self', 'mut self'):
                continue
            # 取参数名 (name: Type)
            if ':' in part:
                param_name = part.split(':')[0].strip()
                param_name = param_name.lstrip('mut ').strip()
                if param_name:
                    params.append(param_name)
        
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
        pattern = r'(?<![.\w])(\w+)\s*(?:!?\s*)?\('
        for match in re.finditer(pattern, body):
            call_name = match.group(1)
            # 排除关键字
            if call_name not in ('if', 'while', 'for', 'match', 'loop', 'fn',
                                 'let', 'mut', 'return', 'Some', 'None', 'Ok', 'Err',
                                 'impl', 'struct', 'enum', 'trait', 'where', 'async', 'await'):
                calls.add(call_name)
        
        # 方法调用
        method_pattern = r'\.(\w+)\s*\('
        for match in re.finditer(method_pattern, body):
            calls.add(match.group(1))
        
        # 路径调用 (如 std::io::read)
        path_pattern = r'(\w+(?:::\w+)+)\s*\('
        for match in re.finditer(path_pattern, body):
            calls.add(match.group(1))
        
        # 宏调用
        macro_pattern = r'(\w+)!\s*(?:\(|\[|\{)'
        for match in re.finditer(macro_pattern, body):
            calls.add(f"{match.group(1)}!")
        
        return list(calls)
