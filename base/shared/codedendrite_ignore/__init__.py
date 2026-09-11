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

from base.shared.codedendrite_ignore.glob_match import _glob_match
from base.shared.codedendrite_ignore.code_dendrite_ignore import CodeDendriteIgnore, create_default_config

__all__ = ['_glob_match', 'CodeDendriteIgnore', 'create_default_config']
