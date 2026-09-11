"""
database.py - 锚点数据库管理
============================
对 anchor_engine_v2 的封装，提供更友好的接口。
"""

import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import asdict

# 添加 codeTree 目录到路径以复用 anchor_engine_v2
_CODE_TREE_PATH = Path(__file__).parent.parent / "codeTree"
if str(_CODE_TREE_PATH) not in sys.path:
    sys.path.insert(0, str(_CODE_TREE_PATH))

from index.codeTree.anchor_engine_v2 import (
    Anchor, _load_db, _save_db, ANCHOR_DB
)


class AnchorDatabase:
    """
    锚点数据库管理类
    
    封装 anchor_engine_v2 的数据库操作，提供更易用的接口。
    """
    
    def __init__(self, root: str):
        """
        初始化锚点数据库
        
        参数:
            root: 项目根目录
        """
        self.root = Path(root)
        self._db_data = None
    
    @property
    def db_data(self) -> Dict:
        """懒加载数据库"""
        if self._db_data is None:
            self._db_data = _load_db(self.root)
        return self._db_data
    
    @property
    def anchors(self) -> Dict[str, Dict]:
        """获取锚点字典（不含元数据）"""
        return self.db_data.get("anchors", {})
    
    def reload(self) -> List[Anchor]:
        """
        重新加载锚点数据库
        
        返回:
            锚点对象列表
        """
        self._db_data = _load_db(self.root)
        return self.get_all_anchors()
    
    def get_all_anchors(self) -> List[Anchor]:
        """
        获取所有锚点
        
        返回:
            Anchor对象列表
        """
        anchors = []
        for anchor_id, data in self.anchors.items():
            if anchor_id.startswith("_"):
                continue
            if not isinstance(data, dict):
                continue
            
            anchors.append(Anchor(
                id=anchor_id,
                file=data.get("file", ""),
                symbol=data.get("symbol"),
                line_start=data.get("line_start"),
                line_end=data.get("line_end"),
                hash=data.get("hash", ""),
                hash_mode=data.get("hash_mode", "struct"),
                description=data.get("description", ""),
                language=data.get("language", "python")
            ))
        
        return anchors
    
    def get_anchor(self, anchor_id: str) -> Optional[Anchor]:
        """
        获取单个锚点
        
        参数:
            anchor_id: 锚点ID
        
        返回:
            Anchor对象，不存在返回None
        """
        data = self.anchors.get(anchor_id)
        if not data or not isinstance(data, dict):
            return None
        
        return Anchor(
            id=anchor_id,
            file=data.get("file", ""),
            symbol=data.get("symbol"),
            line_start=data.get("line_start"),
            line_end=data.get("line_end"),
            hash=data.get("hash", ""),
            hash_mode=data.get("hash_mode", "struct"),
            description=data.get("description", ""),
            language=data.get("language", "python")
        )
    
    def update_anchor(self, anchor: Anchor):
        """
        更新或创建锚点
        
        参数:
            anchor: Anchor对象
        """
        if "anchors" not in self.db_data:
            self.db_data["anchors"] = {}
        
        self.db_data["anchors"][anchor.id] = asdict(anchor)
        _save_db(self.root, self.db_data)
    
    def delete_anchor(self, anchor_id: str) -> bool:
        """
        删除锚点
        
        参数:
            anchor_id: 锚点ID
        
        返回:
            是否成功删除
        """
        if anchor_id in self.anchors:
            del self.db_data["anchors"][anchor_id]
            _save_db(self.root, self.db_data)
            return True
        return False
    
    def get_anchors_by_file(self, file_path: str) -> List[Anchor]:
        """
        获取指定文件的所有锚点
        
        参数:
            file_path: 文件相对路径
        
        返回:
            Anchor对象列表
        """
        # 规范化路径
        normalized = file_path.replace("\\", "/")
        if normalized.startswith("./"):
            normalized = normalized[2:]
        
        result = []
        for anchor in self.get_all_anchors():
            anchor_file = anchor.file.replace("\\", "/")
            if anchor_file.startswith("./"):
                anchor_file = anchor_file[2:]
            
            if anchor_file == normalized or \
               anchor_file.endswith(normalized) or \
               normalized.endswith(anchor_file):
                result.append(anchor)
        
        return result
    
    def get_anchors_by_symbol(self, symbol: str) -> List[Anchor]:
        """
        获取指定符号的所有锚点
        
        参数:
            symbol: 符号名（如 "ClassName.method"）
        
        返回:
            Anchor对象列表
        """
        return [
            a for a in self.get_all_anchors()
            if a.symbol == symbol
        ]
    
    def count(self) -> int:
        """获取锚点总数"""
        return len([k for k in self.anchors if not k.startswith("_")])
    
    def __len__(self) -> int:
        return self.count()
    
    def __contains__(self, anchor_id: str) -> bool:
        return anchor_id in self.anchors
