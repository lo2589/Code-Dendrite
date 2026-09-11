"""
L4_DataFlow 单元测试
====================
测试动态数据流分析系统。
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from relate.dataFlow import (
    analyze_function_flow,
    trace_variable,
    analyze_call_chain,
    get_function_inputs,
    get_function_outputs,
    get_transformations,
    generate_dataflow_html,
    FunctionDataFlow,
    VariableInfo,
    Transformation
)


class TestAnalyzeFunctionFlow:
    """测试函数数据流分析"""
    
    def test_analyze_simple_function(self, tmp_path):
        """测试分析简单函数"""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def add(a: int, b: int) -> int:
    result = a + b
    return result
""")
        
        result = analyze_function_flow(str(test_file), "add")
        
        assert result is not None
        assert len(result.inputs) == 2
        assert result.inputs[0].name == "a"
        assert result.inputs[1].name == "b"
    
    def test_analyze_nonexistent_function(self, tmp_path):
        """测试分析不存在的函数"""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo(): pass")
        
        result = analyze_function_flow(str(test_file), "nonexistent")
        
        assert result is None
    
    def test_analyze_class_method(self, tmp_path):
        """测试分析类方法"""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
class Calculator:
    def add(self, a, b):
        return a + b
""")
        
        result = analyze_function_flow(str(test_file), "Calculator.add")
        
        assert result is not None
    
    def test_analyze_transformations(self, tmp_path):
        """测试变换提取"""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def process(data):
    x = data * 2
    y = x + 10
    return y
""")
        
        result = analyze_function_flow(str(test_file), "process")
        
        assert result is not None
        assert len(result.transformations) > 0
    
    def test_analyze_nonexistent_file(self):
        """测试分析不存在的文件"""
        result = analyze_function_flow("/nonexistent/file.py", "func")
        
        assert result is None


class TestTraceVariable:
    """测试变量追踪"""
    
    def test_trace_input_variable(self, tmp_path):
        """测试追踪输入参数"""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def process(x: int):
    y = x * 2
    return y
""")
        
        result = trace_variable(str(test_file), "process", "x")
        
        assert result is not None
        assert result.variable_name == "x"
        assert result.origin.source == "parameter"
    
    def test_trace_nonexistent_variable(self, tmp_path):
        """测试追踪不存在的变量"""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo(): pass")
        
        result = trace_variable(str(test_file), "foo", "nonexistent")
        
        assert result is None


class TestGetFunctionInputs:
    """测试获取函数输入"""
    
    def test_get_inputs(self, tmp_path):
        """测试获取输入参数"""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def greet(name: str, age: int = 18):
    pass
""")
        
        result = get_function_inputs(str(test_file), "greet")
        
        assert len(result) == 2
        assert result[0].name == "name"
        assert result[1].name == "age"


class TestGetFunctionOutputs:
    """测试获取函数输出"""
    
    def test_get_outputs_with_return_type(self, tmp_path):
        """测试获取有返回类型的输出"""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def get_value() -> int:
    return 42
""")
        
        result = get_function_outputs(str(test_file), "get_value")
        
        assert len(result) == 1
        assert result[0].name == "return"
        assert result[0].var_type == "int"
    
    def test_get_outputs_no_return_type(self, tmp_path):
        """测试获取无返回类型的输出"""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def do_something():
    pass
""")
        
        result = get_function_outputs(str(test_file), "do_something")
        
        # 无返回类型注解时，返回空列表
        assert isinstance(result, list)


class TestGetTransformations:
    """测试获取变换"""
    
    def test_get_transformations(self, tmp_path):
        """测试获取变量变换"""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def compute(x):
    a = x + 1
    b = a * 2
    c = b - 3
    return c
""")
        
        result = get_transformations(str(test_file), "compute")
        
        assert len(result) >= 2


class TestGenerateDataflowHTML:
    """测试数据流HTML生成"""
    
    def test_generate_html(self, tmp_path):
        """测试生成HTML"""
        # 创建项目索引
        import json
        index_path = tmp_path / "index.json"
        index_path.write_text(json.dumps({
            "entry_points": []
        }))
        
        html_path = tmp_path / "output.html"
        
        generate_dataflow_html(str(index_path), str(html_path))
        
        assert html_path.exists()
        
        content = html_path.read_text()
        assert "数据流分析" in content


class TestVariableInfo:
    """测试变量信息"""
    
    def test_to_dict(self):
        """测试转换为字典"""
        info = VariableInfo(
            name="x",
            var_type="int",
            source="parameter",
            line=10
        )
        
        d = info.to_dict()
        
        assert d["name"] == "x"
        assert d["type"] == "int"  # to_dict 中字段名是 "type"
        assert d["source"] == "parameter"


class TestTransformation:
    """测试变换"""
    
    def test_to_dict(self):
        """测试转换为字典"""
        trans = Transformation(
            from_var="x",
            to_var="y",
            operation="multiply",
            line=15,
            code_snippet="y = x * 2"
        )
        
        d = trans.to_dict()
        
        assert d["from_var"] == "x"
        assert d["to_var"] == "y"
        assert d["operation"] == "multiply"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
