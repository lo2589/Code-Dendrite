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
    relative/path.py::symbol
    relative/path.py::category:name
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

from scanner.shared.genome_types import (
    CodeAnchor, AnchorIndex, AnchorCategory,
    ImportInfo, ClassInfo, FunctionInfo, TopLevelBlock
)
from scanner.project.config_detector import ConfigDetector
from scanner.shared.genome_identity import asset_anchor_id, canonical_file_id, symbol_anchor_id
from scanner.shared.codedendrite_ignore import CodeDendriteIgnore
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
                id=symbol_anchor_id(module_name, cls_name),
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
                    id=symbol_anchor_id(module_name, f"{cls_name}.{func_name}"),
                    language="python",
                    category=AnchorCategory.METHOD.value,
                    file=file_path,
                    line_start=lineno, line_end=lineno,
                    name=func_name,
                    code=line.rstrip(),
                    hash=hashlib.sha1(line.encode()).hexdigest()[:12],
                    parent_id=symbol_anchor_id(module_name, cls_name),
                    metadata={"source": "regex_fallback"},
                )
            else:
                anchor = CodeAnchor(
                    id=symbol_anchor_id(module_name, func_name),
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
                    id=asset_anchor_id(
                        module_name,
                        "import",
                        m.group(1).replace(".", "_").replace(",", "_"),
                    ),
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
