"""
ast_hash.py - AST结构哈希计算 (Medium L1-002)
==============================================
计算AST结构哈希，忽略空格、注释、变量名，
只关注代码结构变化。
"""

import ast
import hashlib
import re
from pathlib import Path
from typing import Optional

from parse.hash.file_hash import get_file_hash


def get_ast_hash(file_path: str, language: str = "python") -> str:
    """
    计算AST结构哈希（忽略空格、注释、变量名）
    
    参数:
        file_path: 文件路径
        language: 语言类型 ("python"/"javascript"/"java"/"cpp")
    
    返回:
        8字符结构哈希，解析失败返回空字符串
    
    支持语言:
        - python: 使用ast.parse() + ast.dump()
        - javascript/typescript: 使用正则提取结构
        - java/cpp: 使用正则提取结构
    
    复用: anchor_engine_v2._extract_structural_hash()
    """
    path = Path(file_path)
    if not path.exists():
        return ""
    
    try:
        source = path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return ""
    
    if language == "python":
        return _get_python_ast_hash(source)
    elif language in ("javascript", "typescript", "js", "ts"):
        return _get_js_structure_hash(source)
    elif language in ("java",):
        return _get_java_structure_hash(source)
    elif language in ("cpp", "c", "c++"):
        return _get_cpp_structure_hash(source)
    else:
        # 不支持的语言回退到文件哈希
        return get_file_hash(file_path)


def _short_hash(content: str) -> str:
    """计算8字符SHA-256哈希"""
    return hashlib.sha256(content.encode()).hexdigest()[:8]


def _get_python_ast_hash(source: str) -> str:
    """
    Python AST结构哈希
    
    使用ast.dump()，include_attributes=False忽略行号等属性，
    只保留结构信息。
    """
    try:
        tree = ast.parse(source)
        # 不包含行号等属性，只关注结构
        dump = ast.dump(tree, include_attributes=False)
        return _short_hash(dump)
    except SyntaxError:
        return ""


def _get_js_structure_hash(source: str) -> str:
    """
    JavaScript/TypeScript结构哈希
    
    通过正则提取：
    - 函数声明 (function/async function/arrow function)
    - 类定义
    - 方法签名
    - 导入/导出语句
    
    忽略：注释、空格、字符串内容
    """
    # 移除注释
    source = re.sub(r'//.*?$', '', source, flags=re.MULTILINE)
    source = re.sub(r'/\*.*?\*/', '', source, flags=re.DOTALL)
    
    # 移除字符串内容（保留引号标记）
    source = re.sub(r'"[^"]*"', '""', source)
    source = re.sub(r"'[^']*'", "''", source)
    source = re.sub(r'`[^`]*`', '``', source)
    
    # 提取结构模式
    patterns = []
    
    # 函数声明
    patterns.extend(re.findall(r'(?:async\s+)?function\s+\w+\s*\([^)]*\)', source))
    
    # 类定义
    patterns.extend(re.findall(r'class\s+\w+(?:\s+extends\s+\w+)?', source))
    
    # 箭头函数（带变量名）
    patterns.extend(re.findall(r'(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?\([^)]*\)\s*=>', source))
    
    # 方法定义
    patterns.extend(re.findall(r'(?:async\s+)?\w+\s*\([^)]*\)\s*\{', source))
    
    # import/export
    patterns.extend(re.findall(r'import\s+.*?from', source))
    patterns.extend(re.findall(r'export\s+(?:default\s+)?(?:class|function|const|let|var)', source))
    
    structure = '\n'.join(sorted(patterns))
    return _short_hash(structure) if structure else ""


def _get_java_structure_hash(source: str) -> str:
    """
    Java结构哈希
    
    提取：
    - 类定义（修饰符、类名、继承、实现）
    - 方法签名（修饰符、返回类型、方法名、参数）
    - 字段声明
    """
    # 移除注释
    source = re.sub(r'//.*?$', '', source, flags=re.MULTILINE)
    source = re.sub(r'/\*.*?\*/', '', source, flags=re.DOTALL)
    
    # 移除字符串内容
    source = re.sub(r'"[^"]*"', '""', source)
    
    patterns = []
    
    # 类定义
    patterns.extend(re.findall(
        r'(?:public|private|protected|abstract|final|static|\s)*class\s+\w+(?:\s+extends\s+\w+)?(?:\s+implements\s+[\w,\s]+)?',
        source
    ))
    
    # 接口定义
    patterns.extend(re.findall(
        r'(?:public|private|protected|\s)*interface\s+\w+(?:\s+extends\s+[\w,\s]+)?',
        source
    ))
    
    # 方法签名
    patterns.extend(re.findall(
        r'(?:public|private|protected|abstract|final|static|synchronized|\s)*'
        r'(?:void|\w+(?:<[^>]+>)?)\s+\w+\s*\([^)]*\)',
        source
    ))
    
    structure = '\n'.join(sorted(patterns))
    return _short_hash(structure) if structure else ""


def _get_cpp_structure_hash(source: str) -> str:
    """
    C/C++结构哈希
    
    提取：
    - 类/结构体定义
    - 函数声明/定义
    - 命名空间
    """
    # 移除注释
    source = re.sub(r'//.*?$', '', source, flags=re.MULTILINE)
    source = re.sub(r'/\*.*?\*/', '', source, flags=re.DOTALL)
    
    # 移除字符串内容
    source = re.sub(r'"[^"]*"', '""', source)
    
    patterns = []
    
    # 命名空间
    patterns.extend(re.findall(r'namespace\s+\w+', source))
    
    # 类/结构体
    patterns.extend(re.findall(r'(?:class|struct)\s+\w+(?:\s*:\s*(?:public|private|protected)\s+\w+)?', source))
    
    # 函数（排除模板参数过于复杂的）
    func_pattern = r'(?:virtual\s+|static\s+|inline\s+|explicit\s+)*' \
                   r'(?:\w+(?:::\w+)*(?:<[^>]*>)?(?:\s*\*|\s*&)?)\s+' \
                   r'\w+\s*\([^)]*\)(?:\s*const)?(?:\s*override)?(?:\s*noexcept)?'
    patterns.extend(re.findall(func_pattern, source))
    
    structure = '\n'.join(sorted(patterns))
    return _short_hash(structure) if structure else ""


def get_symbol_ast_hash(file_path: str, symbol: str, language: str = "python") -> str:
    """
    计算特定符号的AST哈希
    
    参数:
        file_path: 文件路径
        symbol: 符号名 (如 "ClassName.method" 或 "function_name")
        language: 语言类型
    
    返回:
        8字符结构哈希
    """
    if language != "python":
        # 非Python暂不支持符号级哈希
        return get_ast_hash(file_path, language)
    
    path = Path(file_path)
    if not path.exists():
        return ""
    
    try:
        source = path.read_text(encoding='utf-8')
        tree = ast.parse(source)
    except (OSError, SyntaxError, UnicodeDecodeError):
        return ""
    
    # 解析符号路径
    parts = symbol.split(".", 1)
    top_name = parts[0]
    method_name = parts[1] if len(parts) > 1 else None
    
    # 查找顶层定义
    target_node = None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == top_name:
                target_node = node
                break
    
    if target_node is None:
        return ""
    
    # 如果需要查找方法
    if method_name and isinstance(target_node, ast.ClassDef):
        for child in target_node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if child.name == method_name:
                    target_node = child
                    break
        else:
            return ""
    
    # 计算该节点的结构哈希
    dump = ast.dump(target_node, include_attributes=False)
    return _short_hash(dump)

def normalize_body(text: str) -> str:
    """Reduce a chunk of source to what a rewrite must change and a reformat cannot.

    Whitespace only. Comments are deliberately left in: stripping them means
    finding comment starts, and `//` lives inside URLs and `#` inside strings, so
    a naive strip turns `"http://a"` and `"http://b"` into the same text — two
    different functions with one fingerprint. Counting a comment-only edit as a
    change costs a needless re-index; missing a real change costs a wrong answer,
    and the current scheme already fails that way.
    """
    return " ".join(str(text).split())


def body_hash(text: str) -> str:
    """A fingerprint of the code itself, with no file, name or line number in it.

    Two identical functions therefore share a hash — that is what makes it
    possible to notice one has moved, or that two siblings really are the same.
    Identity is the anchor id's job; this answers only "is this the same code".
    """
    return _short_hash(normalize_body(text))
