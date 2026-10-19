"""
Kotlin 代码分析器
使用正则表达式进行静态分析
"""
import re
import os
from typing import List, Optional
from scanner.language.base import BaseAnalyzer, FunctionInfo, ModuleInfo, ProjectInfo


class KotlinAnalyzer(BaseAnalyzer):
    """Kotlin 代码分析器"""

    SUPPORTED_EXTENSIONS = ['.kt', '.kts']

    def __init__(self, root_path: str):
        super().__init__(root_path)

    @property
    def language_name(self) -> str:
        return "kotlin"

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
        content = re.sub(r'""".*?"""', '""""""', content, flags=re.DOTALL)
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
        pattern = r'import\s+([\w.]+(?:\.\*)?)'
        imports.extend(re.findall(pattern, source))
        return imports

    def _extract_classes(self, source: str) -> List[str]:
        """提取类、接口、对象名"""
        items = []
        patterns = [
            r'(?:(?:public|private|internal|protected|open|final|abstract|sealed|data|inner|annotation|enum)\s+)*class\s+(\w+)',
            r'(?:(?:public|private|internal)\s+)*interface\s+(\w+)',
            r'(?:(?:public|private|internal)\s+)*object\s+(\w+)',
        ]
        for pattern in patterns:
            items.extend(re.findall(pattern, source))
        return items

    def _extract_class_details(self, source: str, file_path: str) -> List[dict]:
        """提取类的详细信息"""
        classes = []
        class_pattern = r'(?:(?:public|private|internal|protected|open|final|abstract|sealed|data|inner|annotation|enum)\s+)*(?:class|interface|object)\s+(\w+)(?:\s*<[^>]*>)?(?:\s*\([^)]*\))?(?:\s*:\s*[^{]+)?\s*\{'
        
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
        # fun 方法
        method_pattern = r'(?:(?:public|private|internal|protected|open|override|final|abstract|suspend|inline|infix|operator|tailrec)\s+)*fun\s+(?:<[^>]*>\s*)?(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^\{=]+))?'
        
        for match in re.finditer(method_pattern, class_body):
            method_name = match.group(1)
            params_str = match.group(2) or ''
            return_type = match.group(3)
            
            params = self._parse_params(params_str)
            
            line_num = class_start_line + class_body[:match.start()].count('\n')
            
            is_suspend = 'suspend' in class_body[max(0, match.start()-50):match.start()]
            
            func_info = FunctionInfo(
                name=method_name,
                file_path=file_path,
                line_number=line_num,
                parameters=params,
                return_type=return_type.strip() if return_type else None,
                is_async=is_suspend,
                is_method=True,
                class_name=class_name
            )
            
            # 提取方法体中的调用
            method_body = self._get_function_body(class_body, match.end())
            func_info.calls = self._extract_calls(method_body)
            
            methods.append(func_info)
        
        # init 构造器
        init_pattern = r'(?:(?:public|private|internal|protected)\s+)?init\s*\{?'
        for match in re.finditer(init_pattern, class_body):
            func_info = FunctionInfo(
                name='init',
                file_path=file_path,
                line_number=class_start_line + class_body[:match.start()].count('\n'),
                parameters=[],
                is_method=True,
                class_name=class_name
            )
            methods.append(func_info)
        
        return methods

    def _extract_functions(self, source: str, file_path: str) -> List[FunctionInfo]:
        """提取顶层函数"""
        functions = []
        preprocessed = self._preprocess(source)
        
        func_pattern = r'(?:(?:public|private|internal|suspend|inline|infix|operator|tailrec)\s+)*fun\s+(?:<[^>]*>\s*)?(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^\{=]+))?'
        
        for match in re.finditer(func_pattern, preprocessed):
            func_name = match.group(1)
            params_str = match.group(2) or ''
            return_type = match.group(3)
            
            # 检查是否在类内部
            before = preprocessed[:match.start()]
            class_count = len(re.findall(r'\b(?:class|interface|object)\s+\w+[^{]*\{', before))
            brace_balance = before.count('{') - before.count('}')
            
            if class_count > 0 and brace_balance > 0:
                continue
            
            params = self._parse_params(params_str)
            is_suspend = 'suspend' in preprocessed[max(0, match.start()-50):match.start()]
            
            func_info = FunctionInfo(
                name=func_name,
                file_path=file_path,
                line_number=source[:match.start()].count('\n') + 1,
                parameters=params,
                return_type=return_type.strip() if return_type else None,
                is_async=is_suspend,
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
        
        # Kotlin 参数: name: Type = default
        # 需要处理 lambda 类型如 (Int) -> Unit
        depth = 0
        current_param = []
        
        for char in params_str + ',':
            if char in '(<':
                depth += 1
                current_param.append(char)
            elif char in ')>':
                depth -= 1
                current_param.append(char)
            elif char == ',' and depth == 0:
                param = ''.join(current_param).strip()
                if param:
                    # 取参数名
                    if ':' in param:
                        name = param.split(':')[0].strip()
                        # 移除 vararg 等修饰符
                        name = name.replace('vararg', '').replace('crossinline', '').replace('noinline', '').strip()
                        if name:
                            params.append(name)
                current_param = []
            else:
                current_param.append(char)
        
        return params

    def _get_function_body(self, content: str, start_pos: int) -> str:
        """获取函数体"""
        # Kotlin 可能是 { } 或 = 表达式
        rest = content[start_pos:start_pos + 100].strip()
        if rest.startswith('{'):
            brace_start = content.find('{', start_pos)
            return self._get_block_body(content, brace_start)
        elif rest.startswith('='):
            # 表达式函数，找到行尾或下一个顶层声明
            eq_pos = content.find('=', start_pos)
            line_end = content.find('\n', eq_pos)
            if line_end == -1:
                return content[eq_pos + 1:]
            return content[eq_pos + 1:line_end]
        return ""

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
            if call_name not in ('if', 'while', 'for', 'when', 'fun', 'class',
                                 'val', 'var', 'return', 'throw', 'try', 'catch',
                                 'object', 'interface', 'enum', 'data', 'sealed',
                                 'init', 'constructor', 'get', 'set', 'is', 'as', 'in'):
                calls.add(call_name)
        
        # 方法调用
        method_pattern = r'\.(\w+)\s*\('
        for match in re.finditer(method_pattern, body):
            calls.add(match.group(1))
        
        # 包函数调用
        pkg_pattern = r'(\w+)\.(\w+)\s*\('
        for match in re.finditer(pkg_pattern, body):
            calls.add(f"{match.group(1)}.{match.group(2)}")
        
        # 属性访问（可能是 getter）
        property_pattern = r'\.(\w+)(?!\s*\()'
        for match in re.finditer(property_pattern, body):
            prop = match.group(1)
            if prop not in ('this', 'super', 'it'):
                calls.add(prop)
        
        return list(calls)
