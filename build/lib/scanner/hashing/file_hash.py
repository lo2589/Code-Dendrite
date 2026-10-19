"""
file_hash.py - 文件哈希计算
===========================
计算文件的SHA-256哈希（8字符短哈希）
"""

import hashlib
from pathlib import Path


def get_file_hash(file_path: str) -> str:
    """
    计算文件的SHA-256哈希（8字符）
    
    参数:
        file_path: 文件绝对/相对路径
    
    返回:
        8字符哈希，文件不存在或读取失败返回空字符串
    
    异常处理:
        - FileNotFoundError: 返回空字符串
        - PermissionError: 返回空字符串
        - 其他IOError: 返回空字符串
    """
    try:
        content = Path(file_path).read_bytes()
        return hashlib.sha256(content).hexdigest()[:8]
    except (FileNotFoundError, PermissionError, OSError):
        return ""
