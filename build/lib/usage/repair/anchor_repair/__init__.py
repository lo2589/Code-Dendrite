"""
L2_AnchorRepair - 锚点批量修复系统
===================================
提供锚点状态检查和批量修复功能。

主要函数:
- repair_anchors(): 批量修复锚点 (Hard L2-001)
- check_anchor(): 检查单个锚点状态 (Medium L2-002)
- check_anchors_batch(): 批量检查锚点 (Medium L2-003)
- find_affected_anchors(): 找出受影响的锚点 (Medium L2-004)
- on_files_changed(): 文件变更后的同步修复入口 (Medium L2-005)

类:
- AnchorDatabase: 锚点数据库管理
- AnchorStatusType: 锚点状态类型枚举
"""

from analyzer.shared.legacy.anchorRepair.types import AnchorStatusType, AnchorStatus, RepairResult, SyncResult
from usage.repair.anchor_repair.repair import repair_anchors, on_files_changed, find_affected_anchors
from usage.repair.anchor_repair.batch_check import check_anchor, check_anchors_batch, check_all_anchors
from usage.repair.anchor_repair.database import AnchorDatabase

__all__ = [
    'AnchorStatusType',
    'AnchorStatus',
    'RepairResult',
    'SyncResult',
    'repair_anchors',
    'on_files_changed',
    'find_affected_anchors',
    'check_anchor',
    'check_anchors_batch',
    'check_all_anchors',
    'AnchorDatabase',
]
