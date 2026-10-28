"""
codeGenome/cpp_extractor.py - C++ 代码提取器
=============================================
提取 C++ 文件中的所有锚点，包括：
- #include 语句
- using 声明
- 全局/命名空间变量
- 类定义 (class/struct)
- 方法和构造函数/析构函数
- 普通函数
- 命名空间

锚点命名规范:
    relative/path.cpp::symbol
    relative/path.cpp::category:name
"""

import re
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Tuple

from scanner.shared.genome_types import CodeAnchor, AnchorIndex, AnchorCategory
from scanner.shared.genome_identity import asset_anchor_id, canonical_file_id, symbol_anchor_id
from scanner.shared.codedendrite_ignore import CodeDendriteIgnore

class CppExtractor:
    """
    C++ 代码提取器

    使用正则表达式解析 C++ 文件，提取所有代码锚点。
    """

    def __init__(self, project_root: Optional[str] = None):
        self.index = AnchorIndex()
        self.current_file = ""
        self.current_module = ""
        self.project_root = (
            Path(project_root).expanduser().resolve()
            if project_root is not None
            else None
        )
        self.namespaces: List[str] = []

    def extract_file(self, file_path: str) -> AnchorIndex:
        """
        提取单个 C++ 文件的锚点

        参数:
            file_path: C++ 文件路径

        返回:
            AnchorIndex: 锚点索引
        """
        self.index = AnchorIndex()
        self.current_file = file_path
        self.current_module = self._get_module_name(file_path)

        try:
            source = Path(file_path).read_text(encoding='utf-8', errors='ignore')
        except OSError:
            return self.index

        source = self._preprocess(source)

        self._extract_includes(source)
        self._extract_usings(source)
        self._extract_namespaces(source)
        self._extract_classes_and_structs(source)
        self._extract_functions(source)
        self._extract_global_variables(source)

        return self.index

    def extract_directory(self, dir_path: str) -> AnchorIndex:
        """
        提取目录下所有 C++ 文件的锚点

        参数:
            dir_path: 目录路径

        返回:
            AnchorIndex: 锚点索引
        """
        combined_index = AnchorIndex()

        extensions = ['.cpp', '.h', '.hpp', '.cc', '.cxx', '.hxx']
        root_path = Path(dir_path)
        if self.project_root is None:
            self.project_root = root_path.resolve()
        ignore = CodeDendriteIgnore(str(root_path))

        exclude_dirs = set()
        for ext in extensions:
            for cpp_file in root_path.rglob(f'*{ext}'):
                if not ignore.should_scan(cpp_file):
                    continue
                if self._should_exclude(cpp_file, set()):
                    continue

                try:
                    file_index = self.extract_file(str(cpp_file))
                    for anchor in file_index.anchors.values():
                        combined_index.add(anchor)
                except Exception:
                    continue

        self.index = combined_index
        return combined_index

    def _should_exclude(self, path: Path, exclude_dirs: set) -> bool:
        """检查是否应该排除文件"""
        for part in path.parts:
            if part in exclude_dirs:
                return True
        return False

    def _get_module_name(self, file_path: str) -> str:
        """获取与公开 anchor ID 一致的项目相对文件 ID。"""
        return canonical_file_id(file_path, self.project_root)

    def _preprocess(self, source: str) -> str:
        """预处理源代码"""
        source = re.sub(r'//.*?$', '', source, flags=re.MULTILINE)
        source = re.sub(r'/\*.*?\*/', '', source, flags=re.DOTALL)
        return source

    def _compute_hash(self, content: str) -> str:
        """计算内容哈希"""
        return hashlib.sha1(content.encode()).hexdigest()[:12]

    def _get_namespace_prefix(self) -> str:
        """获取命名空间前缀"""
        if self.namespaces:
            return '.'.join(self.namespaces)
        return "global"

    def _extract_includes(self, source: str):
        """提取 #include 语句"""
        include_pattern = re.compile(r'#include\s+[<"]([^>"]+)[>"]')
        module_id = self.current_module

        for match in include_pattern.finditer(source):
            lib_name = match.group(1).split('/')[-1].split('\\')[-1]
            if '<' in match.group(0):
                lib_name = "sys." + lib_name

            anchor_id = asset_anchor_id(module_id, "include", lib_name)
            line = source[:match.start()].count('\n') + 1
            code = match.group(0)

            anchor = CodeAnchor(
                id=anchor_id,
                language="cpp",
                category=AnchorCategory.INCLUDE.value,
                file=self.current_file,
                line_start=line,
                line_end=line,
                name=lib_name,
                code=code,
                hash=self._compute_hash(code),
                metadata={"full_path": match.group(1)}
            )
            self.index.add(anchor)

    def _extract_usings(self, source: str):
        """提取 using 声明"""
        using_pattern = re.compile(r'using\s+(?:namespace\s+)?([^;]+)\s*;')
        module_id = self.current_module
        ns_prefix = self._get_namespace_prefix()

        for match in using_pattern.finditer(source):
            name = match.group(1).strip()
            anchor_id = asset_anchor_id(
                module_id,
                "using",
                name.replace("::", "."),
            )

            line = source[:match.start()].count('\n') + 1
            code = match.group(0)

            anchor = CodeAnchor(
                id=anchor_id,
                language="cpp",
                category=AnchorCategory.USING.value,
                file=self.current_file,
                line_start=line,
                line_end=line,
                name=name,
                code=code,
                hash=self._compute_hash(code)
            )
            self.index.add(anchor)

    def _extract_namespaces(self, source: str):
        """提取命名空间（更新内部状态）"""
        namespace_pattern = re.compile(r'namespace\s+([A-Za-z_][A-Za-z0-9_]*)')
        self.namespaces = [m.group(1) for m in namespace_pattern.finditer(source)]

    def _extract_classes_and_structs(self, source: str):
        """提取类和结构体"""
        class_pattern = re.compile(
            r'(?:template\s*<[^>]{0,200}>\s*)?'
            r'(class|struct)\s+'
            r'([A-Za-z_][A-Za-z0-9_]*)'
            r'(?:\s*:\s*([^{]{0,200}))?'
            r'\s*\{',
            re.DOTALL
        )

        for match in class_pattern.finditer(source):
            is_struct = match.group(1) == 'struct'
            name = match.group(2)
            bases_str = match.group(3) or ""
            ns_prefix = self._get_namespace_prefix()

            bases = self._parse_bases(bases_str)

            class_body = self._extract_class_body(source, match.end())
            line = source[:match.start()].count('\n') + 1

            category = AnchorCategory.STRUCT.value if is_struct else AnchorCategory.CLASS.value
            anchor_id = symbol_anchor_id(self.current_module, name)

            anchor = CodeAnchor(
                id=anchor_id,
                language="cpp",
                category=category,
                file=self.current_file,
                line_start=line,
                line_end=line,
                name=name,
                code=match.group(0),
                hash=self._compute_hash(match.group(0)),
                metadata={"bases": bases, "is_struct": is_struct}
            )
            self.index.add(anchor)

            self._extract_class_methods(class_body, name, line)

    def _parse_bases(self, bases_str: str) -> List[str]:
        """解析基类列表"""
        bases = []
        for part in bases_str.split(','):
            part = part.strip()
            part = re.sub(r'(public|private|protected)\s+', '', part)
            if part:
                bases.append(part)
        return bases

    def _extract_class_body(self, source: str, start: int) -> str:
        """提取类体"""
        brace_pos = source.find('{', start - 1)
        if brace_pos == -1:
            return ""

        depth = 0
        for i, char in enumerate(source[brace_pos:], brace_pos):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    return source[brace_pos+1:i]

        return ""

    def _extract_class_methods(self, class_body: str, class_name: str, class_line: int):
        """提取类的方法"""
        method_pattern = re.compile(
            r'([\w_:*& \t]+?)\s+'
            r'([A-Za-z_][A-Za-z0-9_:]*)'
            r'\s*\('
            r'[^)]{0,500}'
            r'\)\s*(?:const\s*|volatile\s*|override\s*|noexcept\s*|final\s*)?;',
            re.MULTILINE
        )

        for match in method_pattern.finditer(class_body):
            return_type = match.group(1).strip()
            method_name = match.group(2).strip()

            if method_name == class_name:
                method_type = "constructor"
            elif method_name == f"~{class_name}":
                method_type = "destructor"
            else:
                method_type = "method"

            anchor_id = symbol_anchor_id(
                self.current_module,
                f"{class_name}.{method_name}",
            )

            line = class_line + class_body[:match.start()].count('\n')

            anchor = CodeAnchor(
                id=anchor_id,
                language="cpp",
                category=AnchorCategory.METHOD.value,
                file=self.current_file,
                line_start=line,
                line_end=line,
                name=method_name,
                code=match.group(0),
                hash=self._compute_hash(match.group(0)),
                parent_id=symbol_anchor_id(self.current_module, class_name),
                metadata={
                    "return_type": return_type,
                    "method_type": method_type
                }
            )
            self.index.add(anchor)

    def _extract_functions(self, source: str):
        """提取普通函数"""
        function_pattern = re.compile(
            r'(?:template\s*<[^>]{0,200}>\s*)?'
            r'([\w_:*& \t]+?)\s+'
            r'([A-Za-z_][A-Za-z0-9_:]*)'
            r'\s*\('
            r'[^)]{0,500}'
            r'\)\s*(?:const\s*|volatile\s*|noexcept\s*)?\{',
            re.MULTILINE
        )

        ns_prefix = self._get_namespace_prefix()

        for match in function_pattern.finditer(source):
            return_type = match.group(1).strip()
            func_name = match.group(2).strip()

            if '::' in func_name:
                continue

            if func_name.startswith('~'):
                continue

            anchor_id = symbol_anchor_id(self.current_module, func_name)

            line = source[:match.start()].count('\n') + 1

            anchor = CodeAnchor(
                id=anchor_id,
                language="cpp",
                category=AnchorCategory.FUNCTION.value,
                file=self.current_file,
                line_start=line,
                line_end=line,
                name=func_name,
                code=match.group(0),
                hash=self._compute_hash(match.group(0)),
                metadata={"return_type": return_type}
            )
            self.index.add(anchor)

    def _extract_global_variables(self, source: str):
        """提取全局变量"""
        var_pattern = re.compile(
            r'^((?:const|static|extern)\s+)'
            r'([\w_:*& \t]+?)\s+'
            r'([A-Za-z_][A-Za-z0-9_:]*)'
            r'[^;]{0,200};',
            re.MULTILINE
        )

        ns_prefix = self._get_namespace_prefix()

        for match in var_pattern.finditer(source):
            qualifiers = match.group(1).strip()
            var_type = match.group(2).strip()
            var_name = match.group(3).strip()

            if qualifiers or var_type.startswith('typedef'):
                continue

            if '::' in var_name or var_name.startswith('_'):
                continue

            anchor_id = asset_anchor_id(self.current_module, "var", var_name)

            line = source[:match.start()].count('\n') + 1

            anchor = CodeAnchor(
                id=anchor_id,
                language="cpp",
                category=AnchorCategory.VARIABLE.value,
                file=self.current_file,
                line_start=line,
                line_end=line,
                name=var_name,
                code=match.group(0).strip(),
                hash=self._compute_hash(match.group(0)),
                metadata={"var_type": var_type}
            )
            self.index.add(anchor)

    def get_anchors(self) -> AnchorIndex:
        """获取锚点索引"""
        return self.index
