"""
types.py - L2_AnchorRepair 数据类型定义
========================================
"""

import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

# 从 anchor_engine_v2 导入 Anchor 类
_CODE_TREE_PATH = Path(__file__).parent.parent / "codeTree"
if str(_CODE_TREE_PATH) not in sys.path:
    sys.path.insert(0, str(_CODE_TREE_PATH))

try:
    from anchor_engine_v2 import Anchor
except ImportError:
    # 回退：定义一个简化版 Anchor
    @dataclass
    class Anchor:
        """锚点数据结构"""
        id: str
        file: str
        symbol: Optional[str] = None
        line_start: Optional[int] = None
        line_end: Optional[int] = None
        hash: str = ""
        hash_mode: str = "struct"
        description: str = ""
        language: str = "python"


class AnchorStatusType(Enum):
    """锚点状态类型"""
    VALID = "valid"                    # 哈希匹配，锚点有效
    DRIFTED = "drifted"                # 哈希不匹配但符号存在
    MISSING_FILE = "missing_file"      # 文件不存在
    MISSING_SYMBOL = "missing_symbol"  # 符号不存在
    RENAMED = "renamed"                # 可能被重命名


@dataclass
class AnchorStatus:
    """锚点状态"""
    anchor_id: str
    status: AnchorStatusType
    old_hash: str
    new_hash: str
    severity: str                      # "low" | "medium" | "high" | "critical"
    message: str
    suggested_fix: Optional[str] = None  # 建议的修复操作
    
    @property
    def is_valid(self) -> bool:
        return self.status == AnchorStatusType.VALID
    
    @property
    def needs_repair(self) -> bool:
        return self.status in (AnchorStatusType.DRIFTED, AnchorStatusType.RENAMED)
    
    @property
    def is_broken(self) -> bool:
        return self.status in (AnchorStatusType.MISSING_FILE, AnchorStatusType.MISSING_SYMBOL)


@dataclass
class RepairResult:
    """修复结果"""
    anchor_id: str
    success: bool
    action: str                        # "updated" | "deleted" | "skipped" | "error"
    old_hash: str
    new_hash: str
    error: Optional[str] = None
    
    @property
    def is_changed(self) -> bool:
        return self.action == "updated" and self.old_hash != self.new_hash


@dataclass
class SyncResult:
    """同步修复结果"""
    total_anchors: int                 # 数据库中锚点总数
    checked: int                       # 检查的锚点数
    updated: int                       # 更新的锚点数
    failed: int                        # 失败的锚点数
    elapsed_ms: int                    # 耗时（毫秒）
    
    @property
    def success_rate(self) -> float:
        if self.checked == 0:
            return 1.0
        return (self.checked - self.failed) / self.checked
    
    def to_dict(self) -> dict:
        return {
            "total_anchors": self.total_anchors,
            "checked": self.checked,
            "updated": self.updated,
            "failed": self.failed,
            "elapsed_ms": self.elapsed_ms,
            "success_rate": f"{self.success_rate:.1%}"
        }
