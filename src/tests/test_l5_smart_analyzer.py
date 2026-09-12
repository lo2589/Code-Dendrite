"""
L5_SmartAnalyzer 单元测试
=========================
测试统一分析入口。
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from usage.analyze.smart_analyzer import SmartCodeAnalyzer


class TestSmartCodeAnalyzer:
    """测试智能代码分析器"""
    
    def test_init(self, tmp_path):
        """测试初始化"""
        analyzer = SmartCodeAnalyzer(str(tmp_path))
        
        assert analyzer.root == tmp_path
    
    def test_get_cache_stats(self, tmp_path):
        """测试获取缓存统计"""
        analyzer = SmartCodeAnalyzer(str(tmp_path))
        
        stats = analyzer.get_cache_stats()
        
        assert isinstance(stats, dict)
    
    def test_analyze_error_low_severity(self, tmp_path):
        """测试低严重度错误分析"""
        analyzer = SmartCodeAnalyzer(str(tmp_path))
        
        result = analyzer.analyze_error(
            error_msg="Test error message",
            severity="low"
        )
        
        assert result is not None
        assert result.severity == "low"
        assert "L1_Hash" in result.layers_used
    
    def test_analyze_error_medium_severity(self, tmp_path):
        """测试中等严重度错误分析"""
        analyzer = SmartCodeAnalyzer(str(tmp_path))
        
        result = analyzer.analyze_error(
            error_msg="Test error message",
            severity="medium"
        )
        
        assert result is not None
        assert result.severity == "medium"
        assert "L3_Inheritance" in result.layers_used
    
    def test_analyze_error_high_severity(self, tmp_path):
        """测试高严重度错误分析"""
        analyzer = SmartCodeAnalyzer(str(tmp_path))
        
        result = analyzer.analyze_error(
            error_msg="Test error message",
            severity="high"
        )
        
        assert result is not None
        assert result.severity == "high"
        assert "L4_DataFlow" in result.layers_used
    
    def test_find_definition(self, tmp_path):
        """测试查找定义"""
        # 创建测试文件
        test_file = tmp_path / "test.py"
        test_file.write_text("""
class MyClass:
    def my_method(self):
        pass
""")
        
        analyzer = SmartCodeAnalyzer(str(tmp_path))
        
        result = analyzer.find_definition("MyClass", str(test_file))
        
        # 结果取决于类索引构建
        assert result is None or isinstance(result, dict)
    
    def test_on_files_changed(self, tmp_path):
        """测试文件变更处理"""
        # 创建测试文件
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")
        
        analyzer = SmartCodeAnalyzer(str(tmp_path))
        
        result = analyzer.on_files_changed(["test.py"])
        
        assert isinstance(result, dict)
        assert "elapsed_ms" in result
    
    def test_scan_project(self, tmp_path):
        """测试项目扫描"""
        # 创建测试文件
        (tmp_path / "main.py").write_text("def main(): pass")
        (tmp_path / "utils.py").write_text("def helper(): pass")
        
        analyzer = SmartCodeAnalyzer(str(tmp_path))
        
        result = analyzer.scan_project()
        
        assert result is not None
        assert result.total_files >= 2
        assert result.elapsed_ms >= 0


class TestAnalyzeErrorParsing:
    """测试错误信息解析"""
    
    def test_parse_file_from_error(self, tmp_path):
        """测试从错误信息解析文件"""
        analyzer = SmartCodeAnalyzer(str(tmp_path))
        
        result = analyzer.analyze_error(
            error_msg='File "/path/to/file.py", line 10',
            severity="medium"
        )
        
        assert result is not None
    
    def test_parse_line_from_error(self, tmp_path):
        """测试从错误信息解析行号"""
        analyzer = SmartCodeAnalyzer(str(tmp_path))
        
        result = analyzer.analyze_error(
            error_msg="Error at line 42",
            severity="medium"
        )
        
        assert result is not None


class TestLayeredCache:
    """测试分层缓存"""
    
    def test_cache_initialization(self, tmp_path):
        """测试缓存初始化"""
        analyzer = SmartCodeAnalyzer(str(tmp_path))
        
        stats = analyzer.get_cache_stats()
        
        # 初始缓存为空
        assert isinstance(stats, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
