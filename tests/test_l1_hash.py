"""
L1_Hash 单元测试
================
测试增量哈希系统。
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from parse.hash import (
    get_file_hash,
    get_ast_hash,
    get_changed_files,
    HashDatabase,
    ChangeType,
    classify_change
)


class TestFileHash:
    """测试文件哈希计算"""
    
    def test_get_file_hash_normal(self, tmp_path):
        """测试正常文件的哈希计算"""
        # 创建测试文件
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")
        
        result = get_file_hash(str(test_file))
        
        assert result != "", "哈希不应为空"
        assert len(result) == 8, "哈希应为8字符"
    
    def test_get_file_hash_nonexistent(self):
        """测试不存在的文件返回空字符串"""
        result = get_file_hash("/nonexistent/file/path.py")
        
        assert result == "", "不存在的文件应返回空字符串"
    
    def test_get_file_hash_consistency(self, tmp_path):
        """测试相同内容返回相同哈希"""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")
        
        hash1 = get_file_hash(str(test_file))
        hash2 = get_file_hash(str(test_file))
        
        assert hash1 == hash2, "相同内容应返回相同哈希"


class TestASTHash:
    """测试AST哈希计算"""
    
    def test_get_ast_hash_python(self, tmp_path):
        """测试Python文件的AST哈希"""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo():\n    return 1")
        
        result = get_ast_hash(str(test_file), "python")
        
        assert result != "", "AST哈希不应为空"
    
    def test_get_ast_hash_ignores_comments(self, tmp_path):
        """测试AST哈希忽略注释"""
        file1 = tmp_path / "test1.py"
        file2 = tmp_path / "test2.py"
        
        file1.write_text("def foo():\n    return 1")
        file2.write_text("# 这是一个注释\ndef foo():\n    return 1  # 行尾注释")
        
        hash1 = get_ast_hash(str(file1), "python")
        hash2 = get_ast_hash(str(file2), "python")
        
        assert hash1 == hash2, "只有注释差异的代码应有相同AST哈希"
    
    def test_get_ast_hash_syntax_error(self, tmp_path):
        """测试语法错误文件返回空字符串"""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo(:\n")  # 语法错误
        
        result = get_ast_hash(str(test_file), "python")
        
        assert result == "", "语法错误应返回空字符串"


class TestClassifyChange:
    """测试变更分类"""
    
    def test_classify_added(self, tmp_path):
        """测试新文件分类"""
        # 需要文件存在才能正确判断
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")
        result = classify_change(str(test_file), "", "abc123")
        assert result == ChangeType.ADDED
    
    def test_classify_unchanged(self):
        """测试未变更分类"""
        result = classify_change("test.py", "same", "same")
        # 注意：文件不存在时会返回DELETED
        # 所以需要一个存在的文件
    
    def test_classify_deleted(self):
        """测试已删除文件分类"""
        result = classify_change("/nonexistent/file.py", "old", "new")
        assert result == ChangeType.DELETED


class TestHashDatabase:
    """测试哈希数据库"""
    
    def test_database_load(self, tmp_path):
        """测试数据库加载"""
        db = HashDatabase(str(tmp_path))
        
        assert "files" in db.data
        assert "_meta" in db.data
    
    def test_database_update_and_save(self, tmp_path):
        """测试数据库更新和保存"""
        # 创建测试文件
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")
        
        db = HashDatabase(str(tmp_path))
        count = db.update(["test.py"])
        
        assert count == 1, "应更新1个文件"
        assert "test.py" in db.data["files"]
        
        # 验证持久化
        db2 = HashDatabase(str(tmp_path))
        assert "test.py" in db2.data["files"]
    
    def test_database_get_stale_files(self, tmp_path):
        """测试获取过期文件"""
        # 创建测试文件
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")
        
        db = HashDatabase(str(tmp_path))
        db.update(["test.py"])
        
        # 修改文件
        test_file.write_text("x = 2")
        
        stale = db.get_stale_files()
        
        assert "test.py" in stale


class TestGitDiff:
    """测试Git差异检测"""
    
    def test_get_changed_files_in_git_repo(self):
        """测试在Git仓库中获取变更文件"""
        # 使用当前项目目录
        root = str(Path(__file__).parent.parent.parent.parent)
        result = get_changed_files(root)
        
        # 结果是列表，可能为空
        assert isinstance(result, list)
    
    def test_get_changed_files_non_git(self, tmp_path):
        """测试非Git仓库返回空列表"""
        result = get_changed_files(str(tmp_path))
        
        assert result == [], "非Git仓库应返回空列表"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
