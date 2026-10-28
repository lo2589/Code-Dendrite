"""
L2_AnchorRepair 单元测试
=========================
测试锚点批量修复系统。
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer.repair.anchor_repair import (
    AnchorDatabase,
    AnchorStatusType,
    AnchorStatus,
    RepairResult,
    SyncResult,
    check_anchor,
    check_anchors_batch,
    repair_anchors,
    on_files_changed
)
from analyzer.shared.legacy.anchorRepair.types import Anchor


class TestAnchorDatabase:
    """测试锚点数据库"""
    
    def test_reload_empty(self, tmp_path):
        """测试重新加载空数据库"""
        db = AnchorDatabase(str(tmp_path))
        anchors = db.reload()
        
        assert isinstance(anchors, list)
    
    def test_update_and_retrieve_anchor(self, tmp_path):
        """测试更新和检索锚点"""
        db = AnchorDatabase(str(tmp_path))
        
        anchor = Anchor(
            id="test.anchor",
            file="test.py",
            symbol="test_func",
            line_start=1,
            line_end=10,
            hash="abc123",
            hash_mode="struct",
            description="Test anchor",
            language="python"
        )
        
        db.update_anchor(anchor)
        
        retrieved = db.get_anchor("test.anchor")
        
        assert retrieved is not None
        assert retrieved.id == "test.anchor"
        assert retrieved.hash == "abc123"
    
    def test_delete_anchor(self, tmp_path):
        """测试删除锚点"""
        db = AnchorDatabase(str(tmp_path))
        
        anchor = Anchor(
            id="test.to_delete",
            file="test.py",
            hash="xyz789"
        )
        
        db.update_anchor(anchor)
        assert db.get_anchor("test.to_delete") is not None
        
        db.delete_anchor("test.to_delete")
        assert db.get_anchor("test.to_delete") is None
    
    def test_get_anchors_by_file(self, tmp_path):
        """测试按文件获取锚点"""
        db = AnchorDatabase(str(tmp_path))
        
        # 创建多个锚点
        for i in range(3):
            anchor = Anchor(
                id=f"anchor.{i}",
                file="src/module.py",
                hash=f"hash{i}"
            )
            db.update_anchor(anchor)
        
        anchors = db.get_anchors_by_file("src/module.py")
        
        assert len(anchors) == 3


class TestAnchorStatus:
    """测试锚点状态"""
    
    def test_valid_status(self):
        """测试有效状态"""
        status = AnchorStatus(
            anchor_id="test",
            status=AnchorStatusType.VALID,
            old_hash="abc",
            new_hash="abc",
            severity="low",
            message="Valid"
        )
        
        assert status.is_valid
        assert not status.needs_repair
        assert not status.is_broken
    
    def test_drifted_status(self):
        """测试漂移状态"""
        status = AnchorStatus(
            anchor_id="test",
            status=AnchorStatusType.DRIFTED,
            old_hash="abc",
            new_hash="xyz",
            severity="medium",
            message="Drifted"
        )
        
        assert not status.is_valid
        assert status.needs_repair
        assert not status.is_broken
    
    def test_missing_file_status(self):
        """测试文件缺失状态"""
        status = AnchorStatus(
            anchor_id="test",
            status=AnchorStatusType.MISSING_FILE,
            old_hash="abc",
            new_hash="",
            severity="critical",
            message="File missing"
        )
        
        assert not status.is_valid
        assert not status.needs_repair
        assert status.is_broken


class TestSyncResult:
    """测试同步结果"""
    
    def test_success_rate(self):
        """测试成功率计算"""
        result = SyncResult(
            total_anchors=10,
            checked=8,
            updated=5,
            failed=1,
            elapsed_ms=100
        )
        
        assert result.success_rate == 7/8
    
    def test_success_rate_zero_checked(self):
        """测试零检查的成功率"""
        result = SyncResult(
            total_anchors=10,
            checked=0,
            updated=0,
            failed=0,
            elapsed_ms=0
        )
        
        assert result.success_rate == 1.0
    
    def test_to_dict(self):
        """测试转换为字典"""
        result = SyncResult(
            total_anchors=10,
            checked=8,
            updated=5,
            failed=1,
            elapsed_ms=100
        )
        
        d = result.to_dict()
        
        assert "total_anchors" in d
        assert "success_rate" in d
        assert "87.5%" in d["success_rate"]


class TestRepairAnchors:
    """测试锚点修复"""
    
    def test_repair_anchors_empty_list(self, tmp_path):
        """测试空变更列表"""
        result = repair_anchors([], str(tmp_path))
        
        assert result == []
    
    def test_on_files_changed(self, tmp_path):
        """测试文件变更处理"""
        result = on_files_changed([], str(tmp_path))
        
        assert isinstance(result, SyncResult)
        assert result.elapsed_ms >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
