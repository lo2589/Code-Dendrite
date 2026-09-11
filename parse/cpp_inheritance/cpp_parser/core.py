"""
cpp_parser.py - C++ AST 解析器
===============================
使用正则表达式进行 C++ 代码解析，支持：
- 类定义和继承
- 结构体定义
- 模板类
- 命名空间
- 虚函数和 override
- .h/.cpp 自动关联

支持 SLAM 等复杂 C++ 项目。

用法：
    from parse.cpp_inheritance.cpp_parser import parse_cpp_file

    info = parse_cpp_file("/path/to/file.cpp")
    for cls in info.classes:
        print(f"Class: {cls.name}, Bases: {cls.bases}")
"""

import re
from pathlib import Path
from typing import List, Optional, Dict, Set, Tuple

from base.cpp_inheritance.types import (
    CppClassInfo, CppMethodInfo, CppFileInfo,
    CppIncludeInfo, CppNamespaceInfo
)

class CppParser:
    """
    C++ 代码解析器

    使用正则表达式解析 C++ 代码，提取类、结构体、继承关系等信息。
    支持：
    - 普通类
    - 模板类
    - 结构体
    - 命名空间
    - 多继承
    - 虚函数
    - override
    """

    def __init__(self):
        self.class_pattern = re.compile(
            r'(?:template\s*<[^>]*>\s*)?'
            r'(?:export\s+)?'
            r'(?:class|struct)\s+'
            r'([A-Za-z_][A-Za-z0-9_]*)'
            r'(?:\s*:\s*([^{]+))?'
            r'\s*\{',
            re.MULTILINE | re.DOTALL
        )

        self.class_pattern_v2 = re.compile(
            r'(?:template\s*<[^>]*>\s*)?'
            r'(?:export\s+)?'
            r'(?:class|struct)\s+'
            r'([A-Za-z_][A-Za-z0-9_]*)'
            r'(?:\s*:\s*([^{]+?))?'
            r'\s*\{',
            re.MULTILINE | re.DOTALL
        )

        self.method_pattern = re.compile(
            r'(?:template\s*<[^>]*>\s*)?'
            r'((?:[\w_:]+(?:\s*\*|\s*&)?\s*)+?)'  # 返回类型
            r'\s+'
            r'([A-Za-z_][A-Za-z0-9_:]*)'  # 方法名
            r'\s*\('
            r'([^)]*)'  # 参数
            r'\)\s*(?:const|volatile|override|noexcept|final)?',
            re.MULTILINE
        )

        self.template_class_pattern = re.compile(
            r'template\s*<([^>]+)>\s*'
            r'(?:class|struct)\s+'
            r'([A-Za-z_][A-Za-z0-9_]*)',
            re.MULTILINE
        )

        self.include_pattern = re.compile(
            r'#include\s+(?:[<"]([^>"]+)[>"])',
            re.MULTILINE
        )

        self.namespace_pattern = re.compile(
            r'namespace\s+([A-Za-z_][A-Za-z0-9_]*)',
            re.MULTILINE
        )

    def parse_file(self, file_path: str) -> CppFileInfo:
        """
        解析 C++ 文件

        参数：
            file_path: 文件路径

        返回：
            CppFileInfo 对象
        """
        path = Path(file_path)
        if not path.exists():
            return CppFileInfo(file_path=file_path)

        try:
            content = path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return CppFileInfo(file_path=file_path)

        info = CppFileInfo(
            file_path=file_path,
            includes=self._extract_includes(content),
            line_count=len(content.splitlines())
        )

        content = self._preprocess(content)

        info.namespaces = self._extract_namespaces(content)

        classes = self._extract_classes(content, file_path)
        info.classes.extend(classes)

        return info

    def _preprocess(self, content: str) -> str:
        """预处理代码"""
        content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        content = re.sub(r'#.*?$', '', content, flags=re.MULTILINE)
        content = re.sub(r'"[^"]*"', '""', content)
        content = re.sub(r"'[^']*'", "''", content)
        return content

    def _extract_includes(self, content: str) -> List[CppIncludeInfo]:
        """提取 include 语句"""
        includes = []
        for match in self.include_pattern.finditer(content):
            path = match.group(1)
            is_system = path.startswith('<') or not path.startswith('.')
            includes.append(CppIncludeInfo(
                path=path,
                is_system=is_system,
                line=content[:match.start()].count('\n') + 1
            ))
        return includes

    def _extract_namespaces(self, content: str) -> List[CppNamespaceInfo]:
        """提取命名空间"""
        namespaces = []
        seen = set()

        for match in self.namespace_pattern.finditer(content):
            name = match.group(1)
            line = content[:match.start()].count('\n') + 1
            if name not in seen:
                namespaces.append(CppNamespaceInfo(name=name, line=line))
                seen.add(name)

        return namespaces

    def _extract_classes(self, content: str, file_path: str) -> List[CppClassInfo]:
        """提取类和继承信息"""
        classes = []

        current_namespace = self._get_current_namespace(content)

        for match in self.class_pattern_v2.finditer(content):
            class_name = match.group(1)
            bases_str = match.group(2) or ""

            full_name = f"{current_namespace}::{class_name}" if current_namespace else class_name

            bases = self._parse_bases_with_namespace(bases_str, current_namespace)

            line = content[:match.start()].count('\n') + 1

            class_body = self._extract_class_body(content, match.end())

            is_struct = 'struct' in content[max(0, match.start()-20):match.start()]
            is_template = 'template' in content[max(0, match.start()-50):match.start()]

            methods = self._extract_methods(class_body, line)

            templates = self._extract_template_params(content, match.start())

            class_info = CppClassInfo(
                name=full_name,
                file=file_path,
                line=line,
                bases=bases,
                methods=methods,
                templates=templates,
                is_struct=is_struct,
                is_template=is_template
            )

            classes.append(class_info)

        return classes

    def _get_current_namespace(self, content: str) -> str:
        """获取当前位置的命名空间（支持嵌套）"""
        ns_stack = []
        for match in self.namespace_pattern.finditer(content):
            ns_name = match.group(1)
            ns_pos = match.start()
            ns_end_pos = self._find_namespace_end(content, ns_pos)
            ns_stack.append((ns_pos, ns_end_pos, ns_name))

        if not ns_stack:
            return ""

        ns_stack.sort()
        active_ns = []

        for i, (start, end, name) in enumerate(ns_stack):
            active_ns.append(name)
            for j in range(i + 1, len(ns_stack)):
                if start < ns_stack[j][0] < ns_stack[i][1]:
                    active_ns.append(ns_stack[j][2])

        if active_ns:
            return "::".join(active_ns)
        return ""

    def _find_namespace_end(self, content: str, start_pos: int) -> int:
        """查找 namespace 块的结束位置"""
        depth = 0
        for i in range(start_pos, len(content)):
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
                if depth == 0:
                    return i
        return len(content)

    def _parse_bases_with_namespace(self, bases_str: str, current_namespace: str) -> List[str]:
        """解析基类列表（添加命名空间前缀）"""
        bases = self._parse_bases(bases_str)

        if not current_namespace:
            return bases

        result = []
        for base in bases:
            if '::' not in base:
                result.append(f"{current_namespace}::{base}")
            else:
                result.append(base)

        return result

    def _parse_bases(self, bases_str: str) -> List[str]:
        """解析基类列表"""
        bases = []

        if not bases_str.strip():
            return bases

        parts = bases_str.split(',')

        for part in parts:
            part = part.strip()

            part = re.sub(r'public\s+', '', part)
            part = re.sub(r'private\s+', '', part)
            part = re.sub(r'protected\s+', '', part)
            part = re.sub(r'virtual\s+', '', part)

            part = re.sub(r'<[^>]+>', '', part)

            part = part.strip()

            if part and part != ':':
                if '::' in part:
                    base_name = part.split('::')[-1]
                else:
                    base_name = part

                base_name = base_name.strip()
                if base_name:
                    bases.append(base_name)

        return bases

    def _extract_class_body(self, content: str, start: int) -> str:
        """提取类体"""
        brace_pos = content.find('{', start - 1)
        if brace_pos == -1:
            return ""

        depth = 0
        end = brace_pos

        for i, char in enumerate(content[brace_pos:], brace_pos):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    end = i
                    break

        return content[brace_pos+1:end]

    def _extract_methods(self, class_body: str, base_line: int) -> List[CppMethodInfo]:
        """提取类方法"""
        methods = []

        class_body = re.sub(r'//.*?$', '', class_body, flags=re.MULTILINE)
        class_body = re.sub(r'/\*.*?\*/', '', class_body, flags=re.DOTALL)

        line_offset = class_body.count('\n')

        for match in self.method_pattern.finditer(class_body):
            return_type = match.group(1).strip()
            method_name = match.group(2).strip()
            params_str = match.group(3).strip()

            if '~' in method_name:
                continue

            params = [p.strip() for p in params_str.split(',') if p.strip()]

            full_match = match.group(0)
            line_in_body = class_body[:match.start()].count('\n')
            line = base_line + line_in_body

            is_virtual = 'virtual' in full_match
            is_override = 'override' in full_match
            is_const = 'const' in full_match
            is_static = 'static' in full_match

            is_pure_virtual = '=' in full_match and '0' in full_match.split('=')[-1]

            access = 'public'
            if 'private:' in class_body[:match.start() + 100]:
                access = 'private'
            elif 'protected:' in class_body[:match.start() + 100]:
                access = 'protected'

            methods.append(CppMethodInfo(
                name=method_name,
                start_line=line,
                end_line=line,
                is_virtual=is_virtual,
                is_override=is_override,
                is_pure_virtual=is_pure_virtual,
                is_static=is_static,
                is_const=is_const,
                access=access,
                return_type=return_type,
                parameters=params
            ))

        return methods

    def _extract_template_params(self, content: str, start: int) -> List[str]:
        """提取模板参数"""
        templates = []

        template_match = re.search(
            r'template\s*<([^>]+)>\s*(?:class|struct)',
            content[max(0, start-100):start]
        )

        if template_match:
            params = template_match.group(1)
            for param in params.split(','):
                param = param.strip()
                if param.startswith('typename') or param.startswith('class'):
                    param = param.split()[-1].strip()
                templates.append(param)

        return templates
