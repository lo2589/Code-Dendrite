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
from scanner.hashing.database.hash_database import HashDatabase
from scanner.hashing.database.classify_change import classify_change

__all__ = ['ChangeType', 'HashDatabase', 'classify_change']
