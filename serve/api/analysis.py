"""
代码分析接口层 (15 个函数)
=========================
包含 13 个直接转发 + 2 个新实现（analyze_code, search_symbol）。
"""

from typing import Optional, List, Dict

from parse.codeAnalysis.analyzer import (
    get_analyzer,
    analyze_project_structure,
    PythonAnalyzer,
    TypeScriptAnalyzer,
    CppAnalyzer,
    JavaAnalyzer,
    PhpAnalyzer,
    RubyAnalyzer,
    GoAnalyzer,
    RustAnalyzer,
    SwiftAnalyzer,
    KotlinAnalyzer,
    HtmlAnalyzer,
)
from view.codeAnalysis.graph import generate_mermaid_for_project


# ─────────────────────────────────────────────
# 新实现：analyze_code
# ─────────────────────────────────────────────

def analyze_code(file_path: str, language: str = None, root: str = "."):
    """
    分析单个文件的代码结构。

    参数:
        file_path: 文件路径
        language: 编程语言（可选，自动检测）
        root: 项目根目录

    返回:
        ProjectInfo 对象（含 functions, modules, classes 等字段）
    """
    analyzer = get_analyzer(root, language=language)
    # 只分析指定文件
    module = analyzer.analyze_file(file_path)
    return module


# ─────────────────────────────────────────────
# 新实现：search_symbol
# ─────────────────────────────────────────────

def search_symbol(symbol: str, root: str = ".", language: str = None, search_type: str = "definition"):
    """
    搜索符号定义或引用。

    参数:
        symbol: 要搜索的符号名（函数名、类名）
        root: 项目根目录
        language: 编程语言（可选，自动检测）
        search_type: "definition"（默认）或 "references"

    返回:
        匹配结果列表，每个元素包含:
        {
            "name": str,        # 符号名
            "file": str,        # 文件路径
            "line": int,        # 行号
            "type": str,        # "function" | "method" | "class"
            "class_name": str,  # 所属类名（方法时有值）
            "parameters": list, # 参数列表
        }
    """
    analyzer = get_analyzer(root, language=language)
    project_info = analyzer.analyze()

    matches = []
    for func in project_info.functions:
        if search_type == "definition":
            if func.name == symbol or (func.class_name and f"{func.class_name}.{func.name}" == symbol):
                matches.append({
                    "name": func.name,
                    "file": func.file_path,
                    "line": func.line_number,
                    "type": "method" if func.is_method else "function",
                    "class_name": func.class_name,
                    "parameters": func.parameters,
                })
        elif search_type == "references":
            # 搜索调用此符号的位置
            for other_func in project_info.functions:
                if symbol in other_func.calls:
                    matches.append({
                        "name": other_func.name,
                        "file": other_func.file_path,
                        "line": other_func.line_number,
                        "type": "caller",
                        "class_name": other_func.class_name,
                        "content": f"{other_func.name} 调用了 {symbol}",
                    })

    return matches


__all__ = [
    # 直接转发 (13 个)
    'get_analyzer',
    'analyze_project_structure',
    'generate_mermaid_for_project',
    'PythonAnalyzer',
    'TypeScriptAnalyzer',
    'CppAnalyzer',
    'JavaAnalyzer',
    'PhpAnalyzer',
    'RubyAnalyzer',
    'GoAnalyzer',
    'RustAnalyzer',
    'SwiftAnalyzer',
    'KotlinAnalyzer',
    'HtmlAnalyzer',
    # 新实现 (2 个)
    'analyze_code',
    'search_symbol',
]
