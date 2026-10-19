"""
Rust 代码分析器
使用正则表达式进行静态分析
"""
import re
import os
from typing import List, Optional
from scanner.language.base import BaseAnalyzer, FunctionInfo, ModuleInfo, ProjectInfo


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

    # 注释 / raw string / 普通字符串（认转义）/ 字符字面量，一趟扫描，
    # 这样 "https://..." 里的 // 不会被当注释，"\"a\"" 也不会让引号错位吞掉后面的代码
    _MASK_PATTERN = re.compile(
        r'//[^\n]*'
        r'|/\*.*?\*/'
        r'|(?<!\w)b?r(#*)".*?"\1'
        r'|"(?:\\.|[^"\\])*"'
        r"|'(?:\\.|[^'\\\n])'",
        re.DOTALL,
    )

    def _preprocess(self, content: str) -> str:
        """注释和字符串替换为等长空白（保留换行），偏移与原文一一对应，可直接回原文算行号"""
        return self._MASK_PATTERN.sub(lambda m: re.sub(r'[^\n]', ' ', m.group(0)), content)

    @staticmethod
    def _compact_cfg(value: str) -> str:
        """Stable, shell-friendly cfg label for duplicate platform symbols."""
        value = re.sub(r'\s+', '', value)
        return value.replace('"', '').replace("'", "")

    def _extract_attributes(self, source: str, start_pos: int, func_name: str) -> List[dict]:
        """Return directly-attached Rust attributes immediately above a function."""
        line_start = source.rfind('\n', 0, start_pos) + 1
        lines = source[:line_start].splitlines()
        attrs = []
        for line in reversed(lines):
            stripped = line.strip()
            if not stripped:
                if attrs:
                    continue
                break
            match = re.match(r'#\[(.+)\]$', stripped)
            if not match:
                break
            raw = match.group(1).strip()
            item = {"name": raw, "raw": "#[{}]".format(raw)}
            cfg = re.match(r'cfg\s*\((.*)\)\s*$', raw)
            if cfg:
                item["name"] = "cfg"
                item["key"] = self._compact_cfg(cfg.group(1))
            elif raw.startswith("tauri::command"):
                item["name"] = "tauri::command"
                rename = re.search(r'\brename\s*=\s*"([^"]+)"', raw)
                item["key"] = rename.group(1) if rename else func_name
            attrs.append(item)
        attrs.reverse()
        return attrs

    @staticmethod
    def _decode(data: bytes) -> str:
        """UTF-8 → GB18030 → UTF-8(replace)。
        GBK 文件按 UTF-8 ignore 读时首字节被丢、尾字节 0x5C 留成反斜杠（如「乗」），
        紧贴右引号就成了 \\"，字符串一路吞到下一个引号，中间的函数全丢"""
        for encoding in ('utf-8', 'gb18030'):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return data.decode('utf-8', errors='replace')

    def analyze_file(self, file_path: str) -> ModuleInfo:
        with open(file_path, 'rb') as f:
            source = self._decode(f.read())

        module_name = os.path.basename(file_path)
        module_info = ModuleInfo(name=module_name, file_path=file_path, line_number=1)

        module_info.imports = self._extract_imports(source)
        struct_infos = self._extract_struct_infos(source)
        module_info.classes = [item['name'] for item in struct_infos]
        module_info.class_infos = struct_infos

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
        """提取结构体、枚举、trait 名"""
        return [item['name'] for item in self._extract_struct_infos(source)]

    def _extract_struct_infos(self, source: str) -> List[dict]:
        """struct / enum / trait 及起止行（pipeline 按 start_line / end_line 读）。
        在去掉注释和字符串的源码上匹配，注释里的 struct Foo 不算；元组结构体取到分号"""
        preprocessed = self._preprocess(source)
        items = []
        for match in re.finditer(r'\b(?:struct|enum|trait)\s+(\w+)', preprocessed):
            end_pos = self._body_end(preprocessed, match.end())
            items.append({
                'name': match.group(1),
                'start_line': preprocessed[:match.start()].count('\n') + 1,
                'end_line': preprocessed[:end_pos].count('\n') + 1,
            })
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
                line_end=source[:self._body_end(preprocessed, match.end())].count('\n') + 1,
                parameters=params,
                return_type=return_type.strip() if return_type else None,
                is_async='async' in preprocessed[max(0, match.start()-10):match.start()],
                is_method=False,
                decorators=self._extract_attributes(source, match.start(), func_name),
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
                    # impl_body[0] 对应 preprocessed[impl_start]，偏移加回去即原文位置
                    line_number=source[:impl_start + method_match.start()].count('\n') + 1,
                    line_end=source[:impl_start + self._body_end(impl_body, method_match.end())].count('\n') + 1,
                    parameters=params,
                    return_type=return_type.strip() if return_type else None,
                    is_async='async' in impl_body[max(0, method_match.start()-10):method_match.start()],
                    is_method=is_self_method,
                    class_name=struct_name,
                    decorators=self._extract_attributes(source, impl_start + method_match.start(), method_name),
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

    def _body_end(self, content: str, start_pos: int) -> int:
        """函数体结束位置：右大括号；无函数体的声明（trait 里的 fn x();）取分号"""
        brace = content.find('{', start_pos)
        semi = content.find(';', start_pos)
        if brace == -1 or (semi != -1 and semi < brace):
            return semi if semi != -1 else start_pos
        return brace + len(self._get_block_body(content, brace)) + 1

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
