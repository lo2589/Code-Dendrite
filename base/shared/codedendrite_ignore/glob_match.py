"""
codedendrite_ignore.py - CodeDendrite 忽略规则解析器
==================================================
解析 .codedendrite_ignore 配置文件，提供文件扫描排除和隐私保护规则。
"""

import os
import re
import fnmatch
from pathlib import Path
from typing import List, Dict, Set, Optional

def _glob_match(rel_norm: str, pattern: str) -> bool:
    """支持 ** 的路径匹配（rel_norm 和 pattern 均为 / 分隔）"""
    pat = pattern.rstrip("/")
    # 目录前缀：pattern 原本以 / 结尾，匹配路径开头
    is_dir_pattern = pattern.endswith("/")

    # 转为正则
    parts = []
    i = 0
    while i < len(pat):
        if pat[i:i+3] == "**/":
            parts.append("(?:.+/)?")
            i += 3
        elif pat[i:i+2] == "**":
            parts.append(".*")
            i += 2
        elif pat[i] == "*":
            parts.append("[^/]*")
            i += 1
        elif pat[i] == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(pat[i]))
            i += 1

    regex = "^" + "".join(parts)
    if is_dir_pattern:
        regex += "(/|$)"
    else:
        regex += "$"

    return bool(re.match(regex, rel_norm))
