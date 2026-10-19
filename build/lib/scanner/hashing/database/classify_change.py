"""
database.py - 哈希数据库管理
============================
管理文件哈希的持久化存储。
"""

import json
import os
import tempfile
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from scanner.hashing.file_hash import get_file_hash
from scanner.hashing.ast_hash import get_ast_hash

from scanner.hashing.database.change_type import ChangeType

def classify_change(
    file_path: str,
    old_hash: str,
    new_hash: str,
    old_ast_hash: Optional[str] = None,
    new_ast_hash: Optional[str] = None
) -> ChangeType:
    """
    分类变更类型
    
    参数:
        file_path: 文件路径
        old_hash: 旧文件哈希
        new_hash: 新文件哈希
        old_ast_hash: 旧AST哈希（可选）
        new_ast_hash: 新AST哈希（可选）
    
    返回:
        ChangeType枚举值
    """
    # 文件删除
    if not Path(file_path).exists():
        return ChangeType.DELETED
    
    # 新文件
    if not old_hash:
        return ChangeType.ADDED
    
    # 哈希相同，未变化
    if old_hash == new_hash:
        return ChangeType.UNCHANGED
    
    # 哈希不同，检查AST
    if old_ast_hash and new_ast_hash:
        if old_ast_hash == new_ast_hash:
            # AST相同但文件哈希不同 -> 格式变化
            return ChangeType.CHANGED
        else:
            # AST也变了 -> 重构
            return ChangeType.REFACTORED
    
    return ChangeType.CHANGED
