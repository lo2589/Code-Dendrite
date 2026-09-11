"""
inspector.py — 轻量代码导航接口

    list_file_anchors(file_path, root)   → 文件内所有函数/类列表
    find_anchor(keyword, root)           → 按函数名模糊搜索
    get_anchor_source(symbol, root)      → anchor 源码（上下各 +3 行）
    get_anchor_relations(symbol, root)   → 调用者 + 被调用者（一层），带跳转历史
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Optional

from serve.api.inspector.find_anchor import _current_python_range, find_anchor, find_attribute_call_sites, get_anchor_relations
from serve.api.inspector.get_downward_chain import get_anchor_source, get_downward_chain
from serve.api.inspector.get_upward_chain import get_upward_chain, list_file_anchors

__all__ = ['_current_python_range', 'find_anchor', 'find_attribute_call_sites', 'get_anchor_relations', 'get_anchor_source', 'get_downward_chain', 'get_upward_chain', 'list_file_anchors']
