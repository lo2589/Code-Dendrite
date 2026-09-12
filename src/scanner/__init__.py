"""
scanner - 语言扫描器
============================
源码 → 符号 / 行号 / 导入 / 调用点。
============================
统一的多语言代码锚点管理系统。

支持:
- Python 和 C++
- 自动提取 import、类、函数、裸代码块
- Hash 映射和快速定位
- 代码漂移检测

用法:
    from scanner import scan_project

    # 扫描项目
    query = scan_project("/path/to/project")

    # 查找类
    classes = query.find_classes("Robot")

    # 查找裸代码
    bare_code = query.find_bare_code_blocks()

    # 检查变更
    drift = query.check_file_drift("file.py")
"""

from analyzer.shared.legacy.codeGenome.types import (
    CodeAnchor,
    AnchorIndex,
    AnchorCategory,
    Language,
    ImportInfo,
    ClassInfo,
    FunctionInfo,
    TopLevelBlock
)

from scanner.language.python.genome import (
    PythonExtractor,
    extract_python_file,
    extract_python_directory
)

from scanner.language.cpp.genome import (
    CppExtractor,
    extract_cpp_file,
    extract_cpp_directory
)

from scanner.store.database import (
    AnchorDatabase,
    ProjectGenome
)

from scanner.store.api import (
    GenomeQuery,
    create_query,
    scan_project
)

__all__ = [
    # Types
    "CodeAnchor",
    "AnchorIndex",
    "AnchorCategory",
    "Language",
    "ImportInfo",
    "ClassInfo",
    "FunctionInfo",
    "TopLevelBlock",

    # Python
    "PythonExtractor",
    "extract_python_file",
    "extract_python_directory",

    # C++
    "CppExtractor",
    "extract_cpp_file",
    "extract_cpp_directory",

    # Database
    "AnchorDatabase",
    "ProjectGenome",

    # API
    "GenomeQuery",
    "create_query",
    "scan_project"
]

__version__ = "1.0.0"
