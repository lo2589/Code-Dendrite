"""
batch_check.py - 锚点批量检查 (Medium L2-002, L2-003)
======================================================
"""

import sys
from pathlib import Path
from typing import List, Optional

from .types import AnchorStatusType, AnchorStatus

# 添加 codeTree 目录到路径以复用 anchor_engine_v2
_CODE_TREE_PATH = Path(__file__).parent.parent / "codeTree"
if str(_CODE_TREE_PATH) not in sys.path:
    sys.path.insert(0, str(_CODE_TREE_PATH))

from anchor_engine_v2 import (
    Anchor, compute_hash_v2, classify_severity,
    _load_db
)


def check_anchor(anchor: Anchor, root: str) -> AnchorStatus:
    """
    检查单个锚点状态 (Medium L2-002)
    
    参数:
        anchor: Anchor对象
        root: 项目根目录
    
    返回:
        AnchorStatus对象
    """
    root_path = Path(root)
    
    # 计算当前哈希
    current_hash, status, struct_hash = compute_hash_v2(
        file=anchor.file,
        symbol=anchor.symbol,
        line_start=anchor.line_start,
        line_end=anchor.line_end,
        hash_mode=anchor.hash_mode,
        root=root_path
    )
    
    old_hash = anchor.hash
    
    # 判断状态
    if status == "missing_file":
        return AnchorStatus(
            anchor_id=anchor.id,
            status=AnchorStatusType.MISSING_FILE,
            old_hash=old_hash,
            new_hash="",
            severity="critical",
            message=f"文件不存在: {anchor.file}",
            suggested_fix="检查文件是否被删除或重命名"
        )
    
    if status == "missing_symbol":
        return AnchorStatus(
            anchor_id=anchor.id,
            status=AnchorStatusType.MISSING_SYMBOL,
            old_hash=old_hash,
            new_hash="",
            severity="critical",
            message=f"符号不存在: {anchor.symbol} in {anchor.file}",
            suggested_fix="检查符号是否被删除或重命名"
        )
    
    if current_hash == old_hash:
        return AnchorStatus(
            anchor_id=anchor.id,
            status=AnchorStatusType.VALID,
            old_hash=old_hash,
            new_hash=current_hash,
            severity="low",
            message="锚点有效",
            suggested_fix=None
        )
    
    # 哈希不匹配，进一步分类严重程度
    severity = classify_severity(
        old_hash=old_hash,
        new_hash=current_hash,
        old_struct_hash=None,  # 旧结构哈希未存储
        new_struct_hash=struct_hash,
        status="stale"
    )
    
    return AnchorStatus(
        anchor_id=anchor.id,
        status=AnchorStatusType.DRIFTED,
        old_hash=old_hash,
        new_hash=current_hash,
        severity=severity,
        message=f"锚点漂移: {old_hash} → {current_hash}",
        suggested_fix="运行 repair_anchors 更新哈希"
    )


def check_anchors_batch(file_path: str, root: str) -> List[AnchorStatus]:
    """
    批量检查指定文件的所有锚点 (Medium L2-003)
    
    参数:
        file_path: 文件相对路径
        root: 项目根目录
    
    返回:
        该文件所有锚点的状态列表
    """
    root_path = Path(root)
    db_data = _load_db(root_path)
    anchors_db = db_data.get("anchors", {})
    
    # 规范化路径
    normalized_path = file_path.replace("\\", "/")
    if normalized_path.startswith("./"):
        normalized_path = normalized_path[2:]
    
    results = []
    
    for anchor_id, anchor_data in anchors_db.items():
        if anchor_id.startswith("_"):
            continue
        
        if not isinstance(anchor_data, dict):
            continue
        
        anchor_file = anchor_data.get("file", "")
        normalized_anchor = anchor_file.replace("\\", "/")
        if normalized_anchor.startswith("./"):
            normalized_anchor = normalized_anchor[2:]
        
        # 检查是否匹配目标文件
        if normalized_anchor == normalized_path or \
           normalized_anchor.endswith(normalized_path) or \
           normalized_path.endswith(normalized_anchor):
            
            # 构建Anchor对象
            anchor = Anchor(
                id=anchor_id,
                file=anchor_data.get("file", ""),
                symbol=anchor_data.get("symbol"),
                line_start=anchor_data.get("line_start"),
                line_end=anchor_data.get("line_end"),
                hash=anchor_data.get("hash", ""),
                hash_mode=anchor_data.get("hash_mode", "struct"),
                description=anchor_data.get("description", ""),
                language=anchor_data.get("language", "python")
            )
            
            status = check_anchor(anchor, root)
            results.append(status)
    
    return results


def check_all_anchors(root: str) -> List[AnchorStatus]:
    """
    检查所有锚点状态
    
    参数:
        root: 项目根目录
    
    返回:
        所有锚点的状态列表
    """
    root_path = Path(root)
    db_data = _load_db(root_path)
    anchors_db = db_data.get("anchors", {})
    
    results = []
    
    for anchor_id, anchor_data in anchors_db.items():
        if anchor_id.startswith("_"):
            continue
        
        if not isinstance(anchor_data, dict):
            continue
        
        anchor = Anchor(
            id=anchor_id,
            file=anchor_data.get("file", ""),
            symbol=anchor_data.get("symbol"),
            line_start=anchor_data.get("line_start"),
            line_end=anchor_data.get("line_end"),
            hash=anchor_data.get("hash", ""),
            hash_mode=anchor_data.get("hash_mode", "struct"),
            description=anchor_data.get("description", ""),
            language=anchor_data.get("language", "python")
        )
        
        status = check_anchor(anchor, root)
        results.append(status)
    
    return results


def get_stale_anchors(root: str) -> List[AnchorStatus]:
    """
    获取所有过期锚点
    
    参数:
        root: 项目根目录
    
    返回:
        过期锚点的状态列表
    """
    all_statuses = check_all_anchors(root)
    return [s for s in all_statuses if s.needs_repair or s.is_broken]


def get_broken_anchors(root: str) -> List[AnchorStatus]:
    """
    获取所有损坏的锚点（文件/符号不存在）
    
    参数:
        root: 项目根目录
    
    返回:
        损坏锚点的状态列表
    """
    all_statuses = check_all_anchors(root)
    return [s for s in all_statuses if s.is_broken]
