"""
L1_Hash - 增量哈希系统
========================
提供文件哈希计算、AST结构哈希、Git差异检测等功能。

主要函数:
- get_file_hash(): 计算文件SHA-256哈希（8字符）
- get_ast_hash(): 计算AST结构哈希（忽略空格/注释）
- get_changed_files(): 获取Git变更文件列表
- classify_change(): 分类变更类型

类:
- HashDatabase: 哈希数据库管理
- ChangeType: 变更类型枚举
"""

from .file_hash import get_file_hash
from .ast_hash import get_ast_hash
from .git_diff import get_changed_files
from .database import HashDatabase, ChangeType, classify_change

__all__ = [
    'get_file_hash',
    'get_ast_hash', 
    'get_changed_files',
    'HashDatabase',
    'ChangeType',
    'classify_change',
]
