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

from scanner.language.cpp.genome.core import CppExtractor

def extract_cpp_directory(
    dir_path: str,
    project_root: Optional[str] = None,
) -> AnchorIndex:
    """提取 C++ 目录的锚点（便捷函数）"""
    extractor = CppExtractor(project_root=project_root)
    return extractor.extract_directory(dir_path)

def extract_cpp_file(file_path: str) -> AnchorIndex:
    """提取 C++ 文件的锚点（便捷函数）"""
    extractor = CppExtractor()
    return extractor.extract_file(file_path)
