"""
repair.py - 锚点批量修复 (Hard L2-001, Medium L2-004, L2-005)
==============================================================
"""

import time
from pathlib import Path
from typing import List, Tuple, Dict, Any

from analyzer.shared.legacy.anchorRepair.types import AnchorStatusType, AnchorStatus, RepairResult, SyncResult
from analyzer.identity.engine import (
    Anchor, compute_hash_v2, classify_severity,
    _load_db, _save_db, ANCHOR_DB
)


def repair_anchors(changed_files: List[str], root: str) -> List[RepairResult]:
    """
    批量修复锚点 (Hard L2-001)
    
    参数:
        changed_files: 变更文件的相对路径列表
        root: 项目根目录
    
    返回:
        修复结果列表
    
    流程:
        1. 加载锚点数据库
        2. 找出受影响的锚点（文件在changed_files中）
        3. 对每个受影响锚点:
           a. 重新计算哈希
           b. 如果文件/符号存在，更新哈希
           c. 如果文件/符号不存在，标记为失败
        4. 保存数据库
        5. 返回修复结果
    
    同步执行，预期耗时 < 1秒（10个文件）
    """
    results = []
    root_path = Path(root)
    
    # 加载数据库
    db_data = _load_db(root_path)
    anchors_db = db_data.get("anchors", {})
    
    if not anchors_db:
        # 数据库为空或格式不对
        return results
    
    # 收集受影响的锚点
    affected = find_affected_anchors(changed_files, anchors_db)
    
    for anchor_id, anchor_data in affected:
        try:
            # 重新计算哈希
            new_hash, status, struct_hash = compute_hash_v2(
                file=anchor_data.get("file", ""),
                symbol=anchor_data.get("symbol"),
                line_start=anchor_data.get("line_start"),
                line_end=anchor_data.get("line_end"),
                hash_mode=anchor_data.get("hash_mode", "struct"),
                root=root_path
            )
            
            old_hash = anchor_data.get("hash", "")
            
            if status == "ok":
                # 更新哈希
                anchor_data["hash"] = new_hash
                anchors_db[anchor_id] = anchor_data
                
                action = "updated" if old_hash != new_hash else "unchanged"
                results.append(RepairResult(
                    anchor_id=anchor_id,
                    success=True,
                    action=action,
                    old_hash=old_hash,
                    new_hash=new_hash,
                    error=None
                ))
            else:
                # 文件或符号不存在
                results.append(RepairResult(
                    anchor_id=anchor_id,
                    success=False,
                    action="skipped",
                    old_hash=old_hash,
                    new_hash="",
                    error=f"Status: {status}"
                ))
        
        except Exception as e:
            results.append(RepairResult(
                anchor_id=anchor_id,
                success=False,
                action="error",
                old_hash=anchor_data.get("hash", ""),
                new_hash="",
                error=str(e)
            ))
    
    # 保存更新后的数据库
    if any(r.success for r in results):
        db_data["anchors"] = anchors_db
        _save_db(root_path, db_data)
    
    return results


def find_affected_anchors(
    changed_files: List[str],
    anchors_db: Dict[str, Any]
) -> List[Tuple[str, Dict]]:
    """
    找出受变更文件影响的锚点 (Medium L2-004)
    
    参数:
        changed_files: 变更文件列表
        anchors_db: 锚点数据库字典（不含_meta等元数据键）
    
    返回:
        受影响的锚点列表: [(anchor_id, anchor_data), ...]
    
    匹配规则:
        - 锚点的file字段与changed_files中的任一文件匹配
        - 支持相对路径和绝对路径
        - 路径规范化后比较
    """
    affected = []
    
    # 规范化变更文件路径
    normalized_changed = set()
    for f in changed_files:
        # 统一使用正斜杠
        normalized = f.replace("\\", "/")
        normalized_changed.add(normalized)
        # 也添加不带前导./的版本
        if normalized.startswith("./"):
            normalized_changed.add(normalized[2:])
    
    for anchor_id, anchor_data in anchors_db.items():
        # 跳过元数据键
        if anchor_id.startswith("_"):
            continue
        
        if not isinstance(anchor_data, dict):
            continue
        
        anchor_file = anchor_data.get("file", "")
        if not anchor_file:
            continue
        
        # 规范化锚点文件路径
        normalized_anchor = anchor_file.replace("\\", "/")
        if normalized_anchor.startswith("./"):
            normalized_anchor = normalized_anchor[2:]
        
        # 精确匹配
        if normalized_anchor in normalized_changed:
            affected.append((anchor_id, anchor_data))
            continue
        
        # 后缀匹配（处理相对/绝对路径混用）
        for changed_file in normalized_changed:
            if normalized_anchor.endswith(changed_file) or changed_file.endswith(normalized_anchor):
                affected.append((anchor_id, anchor_data))
                break
    
    return affected


def on_files_changed(changed_files: List[str], root: str) -> SyncResult:
    """
    对话结束后的同步修复入口 (Medium L2-005)
    
    参数:
        changed_files: 变更文件列表
        root: 项目根目录
    
    返回:
        同步修复结果
    
    设计原则:
        - 同步执行，不异步
        - 只处理变更文件的锚点
        - 秒级完成
    """
    start = time.time()
    
    root_path = Path(root)
    db_data = _load_db(root_path)
    anchors_db = db_data.get("anchors", {})
    
    # 计算总锚点数（排除元数据键）
    total = len([k for k in anchors_db if not k.startswith("_")])
    
    # 执行修复
    results = repair_anchors(changed_files, root)
    
    elapsed_ms = int((time.time() - start) * 1000)
    
    return SyncResult(
        total_anchors=total,
        checked=len(results),
        updated=sum(1 for r in results if r.success and r.action == "updated"),
        failed=sum(1 for r in results if not r.success),
        elapsed_ms=elapsed_ms
    )


def repair_all_stale(root: str) -> SyncResult:
    """
    修复所有过期锚点
    
    参数:
        root: 项目根目录
    
    返回:
        同步修复结果
    """
    start = time.time()
    
    root_path = Path(root)
    db_data = _load_db(root_path)
    anchors_db = db_data.get("anchors", {})
    
    # 获取所有锚点文件
    all_files = set()
    for anchor_id, anchor_data in anchors_db.items():
        if anchor_id.startswith("_"):
            continue
        if isinstance(anchor_data, dict) and "file" in anchor_data:
            all_files.add(anchor_data["file"])
    
    # 修复所有涉及的文件
    results = repair_anchors(list(all_files), root)
    
    elapsed_ms = int((time.time() - start) * 1000)
    
    total = len([k for k in anchors_db if not k.startswith("_")])
    
    return SyncResult(
        total_anchors=total,
        checked=len(results),
        updated=sum(1 for r in results if r.success and r.action == "updated"),
        failed=sum(1 for r in results if not r.success),
        elapsed_ms=elapsed_ms
    )
