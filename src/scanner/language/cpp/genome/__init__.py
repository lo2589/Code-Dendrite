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
from scanner.language.cpp.genome.extract import extract_cpp_directory, extract_cpp_file

__all__ = ['CppExtractor', 'extract_cpp_directory', 'extract_cpp_file']
