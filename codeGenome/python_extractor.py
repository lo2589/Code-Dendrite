"""
codeGenome/python_extractor.py - Python 代码提取器
=================================================
提取 Python 文件中的所有锚点，包括：
- import 语句
- 顶层赋值
- __main__ 块内的裸语句
- 类定义
- 方法定义
- 函数定义

锚点命名规范:
    py.{module}.{category}.{name}
"""

import ast
import hashlib
import os

try:
    # CPython 内部行切分（与 node.lineno 对齐）；用来按文件缓存切分，避免每个节点重切整文件
    from ast import _splitlines_no_ff as _ast_splitlines
except Exception:
    _ast_splitlines = None
from pathlib import Path
from typing import List, Optional, Dict, Set

from .types import (
    CodeAnchor, AnchorIndex, AnchorCategory,
    ImportInfo, ClassInfo, FunctionInfo, TopLevelBlock
)
from .config_detector import ConfigDetector
from shared.codedendrite_ignore import CodeDendriteIgnore
import re as _re


def _try_fix_python(source: str, e: SyntaxError):
    """尝试修复一个 SyntaxError，返回 (fixed_source, True) 或 (source, False)。"""
    msg = (e.msg or "").lower()
    lineno = e.lineno
    if not lineno:
        return source, False
    lines = source.splitlines(keepends=True)
    if lineno > len(lines):
        return source, False
    line = lines[lineno - 1]

    if 'missing parentheses in call to' in msg:
        fixed = _re.sub(
            r'^(\s*)print\s+(.+?)(\s*)$',
            lambda m: m.group(1) + 'print(' + m.group(2).strip() + ')' + m.group(3),
            line.rstrip('\n'),
        )
        if fixed != line.rstrip('\n'):
            lines[lineno - 1] = fixed + '\n'
            return ''.join(lines), True

    if 'cannot assign to' in msg:
        lines[lineno - 1] = '# ' + line
        return ''.join(lines), True

    if 'multiple exception types must be parenthesized' in msg:
        fixed = _re.sub(
            r'(except\s+[\w.]+(?:\s*,\s*[\w.]+)*)\s*,\s*(\w+)\s*:',
            r'except (\1) as \2:',
            line,
        )
        if fixed != line:
            lines[lineno - 1] = fixed
            return ''.join(lines), True

    return source, False


def _try_fix_python_loop(source: str, initial_err: SyntaxError):
    """迭代修复，最多 10 轮。返回 (source, n_fixes, remaining_err_or_None)。"""
    err = initial_err
    n = 0
    for _ in range(10):
        new_src, fixed = _try_fix_python(source, err)
        if not fixed:
            return source, n, err
        n += 1
        source = new_src
        try:
            ast.parse(source)
            return source, n, None
        except SyntaxError as e2:
            err = e2
    return source, n, err


def _regex_extract_python(source: str, file_path: str, module_name: str) -> 'AnchorIndex':
    """AST 无法解析时的 regex 降级提取，带 metadata source=regex_fallback。"""
    index = AnchorIndex()
    lines = source.splitlines()
    # (indent, class_name) 栈，跟踪当前类上下文
    class_stack: list = []

    for lineno, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if not stripped or stripped.startswith('#'):
            continue
        indent = len(line) - len(stripped)
        # 弹出缩进 >= 当前行的类（当前行与它们同级或更外层）
        class_stack = [(i, n) for i, n in class_stack if i < indent]

        # class 定义
        m = _re.match(r'class\s+(\w+)(?:\s*\(([^)]*)\))?\s*:', stripped)
        if m:
            cls_name = m.group(1)
            bases = [b.strip() for b in (m.group(2) or '').split(',') if b.strip()]
            anchor = CodeAnchor(
                id=f"py.{module_name}.classes.{cls_name}",
                language="python",
                category=AnchorCategory.CLASS.value,
                file=file_path,
                line_start=lineno, line_end=lineno,
                name=cls_name,
                code=line.rstrip(),
                hash=hashlib.sha1(line.encode()).hexdigest()[:12],
                metadata={"bases": bases, "source": "regex_fallback"},
            )
            index.add(anchor)
            class_stack.append((indent, cls_name))
            continue

        # def 定义
        m = _re.match(r'def\s+(\w+)\s*\(', stripped)
        if m:
            func_name = m.group(1)
            if class_stack:
                cls_name = class_stack[-1][1]
                anchor = CodeAnchor(
                    id=f"py.{module_name}.classes.{cls_name}.methods.{func_name}",
                    language="python",
                    category=AnchorCategory.METHOD.value,
                    file=file_path,
                    line_start=lineno, line_end=lineno,
                    name=func_name,
                    code=line.rstrip(),
                    hash=hashlib.sha1(line.encode()).hexdigest()[:12],
                    parent_id=f"py.{module_name}.classes.{cls_name}",
                    metadata={"source": "regex_fallback"},
                )
            else:
                anchor = CodeAnchor(
                    id=f"py.{module_name}.functions.{func_name}",
                    language="python",
                    category=AnchorCategory.FUNCTION.value,
                    file=file_path,
                    line_start=lineno, line_end=lineno,
                    name=func_name,
                    code=line.rstrip(),
                    hash=hashlib.sha1(line.encode()).hexdigest()[:12],
                    metadata={"source": "regex_fallback"},
                )
            index.add(anchor)
            continue

        # 顶层 import
        if indent == 0:
            m = _re.match(r'(?:from\s+\S+\s+)?import\s+(\S+)', stripped)
            if m:
                anchor = CodeAnchor(
                    id=f"py.{module_name}.imports.{m.group(1).replace('.','_').replace(',','_')}",
                    language="python",
                    category=AnchorCategory.IMPORT.value,
                    file=file_path,
                    line_start=lineno, line_end=lineno,
                    name=stripped.rstrip()[:80],
                    code=line.rstrip(),
                    hash=hashlib.sha1(line.encode()).hexdigest()[:12],
                    metadata={"source": "regex_fallback"},
                )
                index.add(anchor)

    return index


class PythonExtractor:
    """
    Python 代码提取器

    使用 AST 解析 Python 文件，提取所有代码锚点。
    """

    def __init__(self):
        self.index = AnchorIndex()
        self.current_file = ""
        self.current_module = ""
        self.config_detector = ConfigDetector()  # 新增：配置检测器

    def extract_file(self, file_path: str) -> AnchorIndex:
        """
        提取单个文件的锚点
            
        参数:
            file_path: Python 文件路径
            
        返回:
            AnchorIndex: 锚点索引（单个文件的）
        """
        temp_index = AnchorIndex()
        # 标准化路径：统一使用正斜杠（跨系统兼容）
        self.current_file = file_path.replace("\\", "/")
        self.current_module = self._get_module_name(file_path)
            
        source = None
        tree = None
        for enc in ('utf-8-sig', 'utf-8', 'gbk', 'latin-1'):
            try:
                source = Path(file_path).read_text(encoding=enc)
                tree = ast.parse(source)
                break
            except SyntaxError as e:
                if enc != 'latin-1':
                    continue
                fixed_src, n_fixes, remaining_err = _try_fix_python_loop(source, e)
                if remaining_err is None:
                    source = fixed_src
                    tree = ast.parse(source)
                    temp_index.auto_fixed.append({
                        "file": file_path,
                        "language": "python",
                        "fixes_applied": n_fixes,
                    })
                    break
                temp_index.parse_failures.append({
                    "file": file_path,
                    "language": "python",
                    "error_type": "SyntaxError",
                    "message": remaining_err.msg or str(remaining_err),
                    "lineno": remaining_err.lineno,
                })
                # regex 降级：尽力提取 class/def/import
                regex_index = _regex_extract_python(
                    source, self.current_file, self.current_module
                )
                for anchor in regex_index.anchors.values():
                    temp_index.add(anchor)
                return temp_index
            except OSError:
                return temp_index
        if tree is None:
            return temp_index
            
        # 判断是否为配置文件
        is_config = self._is_config_file(Path(file_path))
            
        if is_config:
            # 配置文件：只提取关键信息，不深入解析
            self._extract_config_metadata(tree, source, temp_index)
        else:
            # 源代码：完整解析
            self._extract_imports(tree, source, temp_index)
            self._extract_top_level_assigns(tree, source, temp_index)
            self._extract_top_level_statements(tree, source, temp_index)
            self._extract_classes_and_functions(tree, source, temp_index)
            
        for anchor in temp_index.anchors.values():
            self.index.add(anchor)
            
        return temp_index

    def extract_directory(self, dir_path: str) -> AnchorIndex:
        """
        提取目录下所有 Python 文件的锚点

        参数:
            dir_path: 目录路径

        返回:
            AnchorIndex: 锚点索引
        """
        self.index = AnchorIndex()

        root_path = Path(dir_path)
        ignore = CodeDendriteIgnore(str(root_path))

        def _iter_py(root_p):
            for dirpath, dirnames, filenames in os.walk(root_p):
                dp = Path(dirpath)
                dirnames[:] = [d for d in dirnames if ignore.should_scan(dp / d / "_x.py")]
                for fname in filenames:
                    if fname.endswith(".py"):
                        yield dp / fname

        for py_file in _iter_py(root_path):
            if not ignore.should_scan(py_file):
                continue
            if self._should_exclude(py_file):
                continue
            try:
                file_index = self.extract_file(str(py_file))
                for anchor in file_index.anchors.values():
                    self.index.add(anchor)
                self.index.parse_failures.extend(file_index.parse_failures)
                self.index.auto_fixed.extend(file_index.auto_fixed)
            except Exception:
                continue

        return self.index

    def _should_exclude(self, path: Path) -> bool:
        """检查是否应该排除文件"""
        return False
            
        for part in path.parts:
            if part in exclude_dirs:
                return True
            
        # 新增：智能识别配置文件（使用相似度比较）
        if self._is_config_file(path):
            return True
            
        return False
        
    def _is_config_file(self, path: Path) -> bool:
        """
        智能识别配置文件
            
        使用多维度特征向量 + 余弦相似度判断
        """
        # Level 1: 路径快速判断（覆盖 90% 情况）
        config_dir_patterns = ['configs', 'configurations', 'conf']
        for part in path.parts:
            if part in config_dir_patterns:
                return True
            
        # Level 2: 文件名模式
        name = path.name.lower()
        if any(kw in name for kw in ['_config', '_base_', '_default', '_preset']):
            return True
            
        return False

    def _get_module_name(self, file_path: str) -> str:
        """获取模块名"""
        path = Path(file_path)
        return path.stem
    
    def _extract_config_metadata(self, tree: ast.AST, source: str, target_index: AnchorIndex):
        """
        提取配置文件的元数据（轻量级）
        
        策略:
        - 只记录文件路径的词向量表示
        - 添加 format tag 用于搜索和关联
        - 不重复存储详细的格式信息（需要时再解析）
        """
        module_id = self.current_module
        file_path = Path(self.current_file)
        
        # 创建基础锚点 - 只有文件信息和词向量
        anchor_id = f"py.{module_id}.config.file"
        
        # 代码内容：只包含文件名和关键标签
        code_content = f"# Config: {file_path.name}"
        
        # 快速检测格式类型（用于添加 tag，不存储详细信息）
        try:
            config_info = self.config_detector.detect_config_format(file_path)
            if config_info and config_info.get('format') != 'unknown':
                # 添加格式标签到代码中（用于搜索）
                fmt = config_info.get('format')
                code_content += f"\n# @format:{fmt}"
                
                # 如果有数据集，也添加标签
                dataset = config_info.get('dataset')
                if dataset:
                    code_content += f"\n# @dataset:{dataset}"
        except Exception:
            pass
        
        anchor = CodeAnchor(
            id=anchor_id,
            language="py",
            category=AnchorCategory.ASSIGN.value,
            file=self.current_file,
            line_start=1,
            line_end=1,
            name=f"config_{module_id}",
            code=code_content,
            hash=self._compute_hash(code_content),
            metadata={
                'is_config': True,
                # 只存最核心的 tag，不存详细数据
                'tags': self._extract_tags_from_code(source),
            }
        )
        target_index.add(anchor)
    
    def _extract_tags_from_code(self, source: str) -> List[str]:
        """
        从源代码中提取关键词作为 tag（用于搜索）
        
        返回:
            ['mmdet', 'coco', 'detection'] 这样的标签列表
        """
        import re
        
        tags = set()
        lines = source.split('\n')[:30]  # 只看前 30 行
        content = '\n'.join(lines)
        
        # 提取关键词模式
        patterns = {
            'mmdet': r'_base_',
            'coco': r'CocoDataset|data/coco',
            'voc': r'VOCDataset|data/VOC',
            'cityscapes': r'CityscapesDataset',
            'rcnn': r'RCNN',
            'yolo': r'YOLO',
            'transformer': r'Transformer',
            'ssd': r'SSD',
        }
        
        for tag, pattern in patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                tags.add(tag)
        
        return sorted(list(tags))

    def _get_source(self, node: ast.AST, source: str) -> str:
        """获取 AST 节点对应的源代码。

        等价于 ast.get_source_segment，但【整文件只 splitlines 一次】（按 source 身份缓存）。
        原实现每个 method/class/function 节点都 get_source_segment -> 内部重切整文件，
        O(节点数 × 文件大小)；sympy/matplotlib 的超大文件直接平方爆炸卡死。
        """
        try:
            if node.end_lineno is None or node.end_col_offset is None:
                return ""
            lineno = node.lineno - 1
            end_lineno = node.end_lineno - 1
            col = node.col_offset
            end_col = node.end_col_offset
        except AttributeError:
            return ast.get_source_segment(source, node) or ""
        if _ast_splitlines is None:
            return ast.get_source_segment(source, node) or ""
        if getattr(self, "_gss_src", None) is not source:   # 同一文件的所有节点共用一次切分
            self._gss_src = source
            self._gss_lines = _ast_splitlines(source)
        lines = self._gss_lines
        try:
            if end_lineno == lineno:
                return lines[lineno].encode()[col:end_col].decode()
            first = lines[lineno].encode()[col:].decode()
            last = lines[end_lineno].encode()[:end_col].decode()
            return "".join([first, *lines[lineno + 1:end_lineno], last])
        except (IndexError, UnicodeDecodeError):
            return ast.get_source_segment(source, node) or ""

    def _compute_hash(self, content: str) -> str:
        """计算内容哈希"""
        return hashlib.sha1(content.encode()).hexdigest()[:12]

    def _extract_imports(self, tree: ast.AST, source: str, target_index: AnchorIndex):
        """提取 import 语句"""
        module_id = self.current_module

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_anchor = self._create_import_anchor(node, source, module_id)
                if import_anchor:
                    target_index.add(import_anchor)

    def _create_import_anchor(self, node: ast.AST, source: str, module_id: str) -> Optional[CodeAnchor]:
        """创建 import 锚点"""
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name
                anchor_id = f"py.{module_id}.imports.{name}"

                code = self._get_source(node, source)
                lines = (node.col_offset + 1, node.end_lineno or node.col_offset + 1)

                return CodeAnchor(
                    id=anchor_id,
                    language="py",
                    category=AnchorCategory.IMPORT.value,
                    file=self.current_file,
                    line_start=lines[0],
                    line_end=lines[1],
                    name=name,
                    code=code,
                    hash=self._compute_hash(code)
                )

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                name = alias.asname or alias.name
                anchor_id = f"py.{module_id}.imports.{name}"

                code = self._get_source(node, source)
                lines = (node.col_offset + 1, node.end_lineno or node.col_offset + 1)

                return CodeAnchor(
                    id=anchor_id,
                    language="py",
                    category=AnchorCategory.IMPORT.value,
                    file=self.current_file,
                    line_start=lines[0],
                    line_end=lines[1],
                    name=name,
                    code=code,
                    hash=self._compute_hash(code),
                    metadata={"from_module": module}
                )

        return None

    def _extract_top_level_assigns(self, tree: ast.AST, source: str, target_index: AnchorIndex):
        """
        提取顶层赋值语句
            
        策略:
        - 将连续的赋值语句合并为一个片段
        - 而不是每个赋值都创建单独的锚点
        """
        module_id = self.current_module
            
        # 收集所有顶层赋值节点
        assign_nodes = []
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                assign_nodes.append(node)
            
        if not assign_nodes:
            return
            
        # 按行号排序
        assign_nodes.sort(key=lambda n: n.lineno)
            
        # 分组：所有顶层赋值归为一组（不管中间有多少空行）
        # 只要没有被函数/类定义打断，就视为一个整体
        if assign_nodes:
            self._add_assign_group_anchor(assign_nodes, source, module_id, 1, target_index)
    
    def _add_assign_group_anchor(self, nodes: List[ast.AST], source: str, 
                                module_id: str, group_idx: int,
                                target_index: AnchorIndex):
        """
        为一组连续的赋值语句创建单个锚点
        
        参数:
            nodes: AST 节点列表
            source: 源代码
            module_id: 模块 ID
            group_idx: 组序号
            target_index: 目标索引
        """
        # 合并代码
        code_segments = []
        var_names = []
        for node in nodes:
            code = self._get_source(node, source)
            if code:
                code_segments.append(code)
            
            # 收集变量名
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
                var_names.extend(targets)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    var_names.append(node.target.id)
        
        merged_code = '\n\n'.join(code_segments)
        
        # 计算行范围
        start_line = min(getattr(n, 'lineno', 0) for n in nodes)
        end_line = max(getattr(n, 'end_lineno', n.lineno) for n in nodes)
        
        anchor_id = f"py.{module_id}.assigns.block_{group_idx}"
        
        anchor = CodeAnchor(
            id=anchor_id,
            language="py",
            category=AnchorCategory.ASSIGN.value,
            file=self.current_file,
            line_start=start_line,
            line_end=end_line,
            name=f"block_{group_idx}",
            code=merged_code,
            hash=self._compute_hash(merged_code),
            metadata={
                "targets": var_names,
                "is_merged": True,
                "statement_count": len(nodes)
            }
        )
        target_index.add(anchor)

    def _extract_top_level_statements(self, tree: ast.AST, source: str, target_index: AnchorIndex):
        """
        提取顶层语句（裸代码块）
            
        策略:
        - 将连续的裸代码合并为一个片段
        - 每个片段创建一个 anchor
        - 而不是每行都创建单独的 anchor
        """
        module_id = self.current_module
            
        # 收集所有顶层节点
        top_level_nodes = []
        for node in tree.body:
            # 跳过已经有专门处理的节点类型
            if isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign, 
                                ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
                
            # 检查是否是 main guard
            if isinstance(node, ast.If):
                test = node.test
                is_main_guard = (
                    isinstance(test, ast.Compare) and
                    isinstance(test.left, ast.Name) and
                    test.left.id == "__name__" and
                    len(test.ops) == 1 and
                    isinstance(test.ops[0], ast.Eq) and
                    isinstance(test.comparators[0], ast.Constant) and
                    test.comparators[0].value == "__main__"
                )
                    
                if is_main_guard:
                    # main guard 单独处理
                    self._add_main_guard_anchor(node, source, module_id, target_index)
                    continue
                
            top_level_nodes.append(node)
            
        # 将连续的裸代码合并为片段
        if not top_level_nodes:
            return
            
        # 按行号排序
        top_level_nodes.sort(key=lambda n: n.lineno)
            
        # 分组：所有顶层裸代码归为一组（不管中间有多少空行）
        # 只要没有被函数/类定义打断，就视为一个整体
        if top_level_nodes:
            self._add_statement_group_anchor(top_level_nodes, source, module_id, 1, target_index)
        
    def _add_statement_group_anchor(self, nodes: List[ast.AST], source: str, 
                                   module_id: str, group_idx: int, 
                                   target_index: AnchorIndex):
        """
        为一组连续的裸代码创建单个锚点
            
        参数:
            nodes: AST 节点列表
            source: 源代码
            module_id: 模块 ID
            group_idx: 组序号
            target_index: 目标索引
        """
        # 合并代码
        code_segments = []
        for node in nodes:
            code = self._get_source(node, source)
            if code:
                code_segments.append(code)
            
        merged_code = '\n\n'.join(code_segments)
            
        # 计算行范围
        start_line = min(getattr(n, 'lineno', 0) for n in nodes)
        end_line = max(getattr(n, 'end_lineno', n.lineno) for n in nodes)
            
        anchor_id = f"py.{module_id}.statements.block_{group_idx}"
            
        anchor = CodeAnchor(
            id=anchor_id,
            language="py",
            category=AnchorCategory.STATEMENT.value,
            file=self.current_file,
            line_start=start_line,
            line_end=end_line,
            name=f"block_{group_idx}",
            code=merged_code,
            hash=self._compute_hash(merged_code),
            metadata={
                "context": "top_level",
                "statement_count": len(nodes),
                "is_merged": True
            }
        )
        target_index.add(anchor)
        
    def _add_main_guard_anchor(self, node: ast.If, source: str, 
                               module_id: str, target_index: AnchorIndex):
        """添加 main guard 锚点"""
        block_count = len([a for a in target_index.anchors.values()
                          if a.category == AnchorCategory.STATEMENT.value])
            
        main_guard_anchor_id = f"py.{module_id}.__main__.guard"
        code = self._get_source(node, source)
        lines = (node.lineno, node.end_lineno or node.lineno)
            
        anchor = CodeAnchor(
            id=main_guard_anchor_id,
            language="py",
            category=AnchorCategory.MAIN_BLOCK.value,
            file=self.current_file,
            line_start=lines[0],
            line_end=lines[1],
            name="__main__ guard",
            code=code,
            hash=self._compute_hash(code),
            metadata={"is_main_guard": True}
        )
        target_index.add(anchor)

    def _add_statement_anchor(self, node: ast.AST, source: str, module_id: str,
                             parent_id: Optional[str], context: str, target_index: AnchorIndex):
        """添加语句锚点"""
        node_type = type(node).__name__
        if node_type == "Expr" and isinstance(node.value, (ast.Call, ast.BinOp, ast.Name, ast.Attribute)):
            node_type = "statement"

        block_count = len([a for a in target_index.anchors.values()
                          if a.category == AnchorCategory.STATEMENT.value])

        anchor_id = f"py.{module_id}.statements.block_{block_count + 1}"

        code = self._get_source(node, source)
        if code:
            lines = (node.lineno, node.end_lineno or node.lineno)

            anchor = CodeAnchor(
                id=anchor_id,
                language="py",
                category=AnchorCategory.STATEMENT.value,
                file=self.current_file,
                line_start=lines[0],
                line_end=lines[1],
                name=f"block_{block_count + 1}",
                code=code,
                hash=self._compute_hash(code),
                parent_id=parent_id or "",
                metadata={"context": context, "statement_type": node_type}
            )
            target_index.add(anchor)

    def _extract_classes_and_functions(self, tree: ast.AST, source: str, target_index: AnchorIndex):
        """提取类和函数"""
        module_id = self.current_module

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                self._extract_class(node, source, module_id, target_index)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._extract_function(node, source, module_id, None, target_index)

    def _extract_class(self, node: ast.ClassDef, source: str, module_id: str, target_index: AnchorIndex):
        """提取类定义"""
        class_id = f"py.{module_id}.classes.{node.name}"
        bases = [self._get_base_name(base) for base in node.bases]

        code = self._get_source(node, source)
        lines = (node.lineno, node.end_lineno or node.lineno)

        decorators = [self._extract_decorator_info(d, source) for d in node.decorator_list]

        anchor = CodeAnchor(
            id=class_id,
            language="py",
            category=AnchorCategory.CLASS.value,
            file=self.current_file,
            line_start=lines[0],
            line_end=lines[1],
            name=node.name,
            code=code,
            hash=self._compute_hash(code),
            metadata={
                "bases": bases,
                "decorators": decorators
            }
        )
        target_index.add(anchor)

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._extract_method(item, source, module_id, node.name, target_index)
            elif isinstance(item, ast.ClassDef):
                self._extract_class(item, source, module_id, target_index)

    def _extract_method(self, node: ast.FunctionDef, source: str, module_id: str, class_name: str, target_index: AnchorIndex):
        """提取方法"""
        method_id = f"py.{module_id}.classes.{class_name}.methods.{node.name}"

        code = self._get_source(node, source)
        lines = (node.lineno, node.end_lineno or node.lineno)

        params = [arg.arg for arg in node.args.args]
        decorators = [self._extract_decorator_info(d, source) for d in node.decorator_list]

        anchor = CodeAnchor(
            id=method_id,
            language="py",
            category=AnchorCategory.METHOD.value,
            file=self.current_file,
            line_start=lines[0],
            line_end=lines[1],
            name=node.name,
            code=code,
            hash=self._compute_hash(code),
            parent_id=f"py.{module_id}.classes.{class_name}",
            metadata={
                "parameters": params,
                "decorators": decorators,
                "is_async": isinstance(node, ast.AsyncFunctionDef)
            }
        )
        target_index.add(anchor)

        class_anchor = target_index.get(f"py.{module_id}.classes.{class_name}")
        if class_anchor:
            class_anchor.children_ids.append(method_id)

    def _extract_function(self, node: ast.FunctionDef, source: str, module_id: str, parent_id: Optional[str], target_index: AnchorIndex):
        """提取函数定义"""
        func_id = f"py.{module_id}.functions.{node.name}"

        code = self._get_source(node, source)
        lines = (node.lineno, node.end_lineno or node.lineno)

        params = [arg.arg for arg in node.args.args]
        decorators = [self._extract_decorator_info(d, source) for d in node.decorator_list]

        anchor = CodeAnchor(
            id=func_id,
            language="py",
            category=AnchorCategory.FUNCTION.value,
            file=self.current_file,
            line_start=lines[0],
            line_end=lines[1],
            name=node.name,
            code=code,
            hash=self._compute_hash(code),
            parent_id=parent_id or "",
            metadata={
                "parameters": params,
                "decorators": decorators,
                "is_async": isinstance(node, ast.AsyncFunctionDef)
            }
        )
        target_index.add(anchor)

    def _extract_decorator_info(self, node: ast.AST, source: str) -> dict:
        source_text = self._get_source(node, source)
        key = None
        name = None
        func_node = node
        if isinstance(node, ast.Call):
            func_node = node.func
            if node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    key = first.value
        if isinstance(func_node, ast.Name):
            name = func_node.id
        elif isinstance(func_node, ast.Attribute):
            name = func_node.attr
        return {"source": source_text, "name": name, "key": key}

    def _get_base_name(self, node: ast.AST) -> str:
        """获取基类名称"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return self._get_base_name(node.value) + "." + node.attr
        elif isinstance(node, ast.Subscript):
            return self._get_base_name(node.value)
        return ""

    def get_anchors(self) -> AnchorIndex:
        """获取锚点索引"""
        return self.index


def extract_python_file(file_path: str) -> AnchorIndex:
    """提取 Python 文件的锚点（便捷函数）"""
    extractor = PythonExtractor()
    return extractor.extract_file(file_path)


def extract_python_directory(dir_path: str) -> AnchorIndex:
    """提取 Python 目录的锚点（便捷函数）"""
    extractor = PythonExtractor()
    return extractor.extract_directory(dir_path)
