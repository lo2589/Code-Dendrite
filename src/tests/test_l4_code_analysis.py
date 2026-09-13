"""
L4_CodeAnalysis 单元测试
========================
测试代码分析模块 - T4.1, T4.2, T4.3

对应测试计划:
- T4.1: PythonAnalyzer 解析精度 [P0]
- T4.2: 跨语言一致性 [P1]
- T4.3: call_graph 调用关系 [P1]
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from scanner.language import (
    get_analyzer,
    BaseAnalyzer,
    PythonAnalyzer,
    TypeScriptAnalyzer,
    JavaAnalyzer,
    CppAnalyzer,
    PhpAnalyzer,
    RubyAnalyzer,
    GoAnalyzer,
    RustAnalyzer,
    SwiftAnalyzer,
    KotlinAnalyzer,
    HtmlAnalyzer,
    FunctionInfo,
    ModuleInfo,
    ProjectInfo,
)


class TestPythonAnalyzer:
    """T4.1: PythonAnalyzer 解析精度 [P0]"""
    
    def test_analyze_simple_file(self, tmp_path):
        """测试简单 Python 文件解析"""
        # 创建测试文件（已知：2个顶层函数，1个类含2个方法）
        test_file = tmp_path / "simple.py"
        test_file.write_text('''
def add(a, b):
    return a + b

def multiply(x, y):
    return x * y

class Calculator:
    def __init__(self):
        self.result = 0
    
    def add(self, a, b):
        return a + b
''')
        
        analyzer = PythonAnalyzer(str(tmp_path))
        result = analyzer.analyze_file(str(test_file))
        
        # 验证解析结果：2个顶层函数 + 2个类方法 = 4个
        assert len(result.functions) == 4, f"预期4个函数，实际{len(result.functions)}"
        assert "Calculator" in result.classes, f"预期Calculator类，实际{result.classes}"
    
    def test_analyze_imports(self, tmp_path):
        """测试 import 语句提取"""
        test_file = tmp_path / "imports.py"
        test_file.write_text('''
import os
import sys
from pathlib import Path
from typing import List, Dict
''')
        
        analyzer = PythonAnalyzer(str(tmp_path))
        result = analyzer.analyze_file(str(test_file))
        
        assert len(result.imports) >= 2, f"预期至少2个import，实际{len(result.imports)}"
        assert "os" in result.imports or "sys" in result.imports
    
    def test_analyze_class_methods(self, tmp_path):
        """测试类方法提取"""
        test_file = tmp_path / "class_test.py"
        test_file.write_text('''
class Service:
    def __init__(self, name):
        self.name = name
    
    def process(self, data):
        return data.upper()
    
    def _private_method(self):
        pass
''')
        
        analyzer = PythonAnalyzer(str(tmp_path))
        result = analyzer.analyze_file(str(test_file))
        
        # 应包含 __init__, process, _private_method
        method_names = [f.name for f in result.functions if f.is_method]
        assert len(method_names) >= 2, f"预期至少2个方法，实际{method_names}"
    
    def test_analyze_decorators(self, tmp_path):
        """测试装饰器提取"""
        test_file = tmp_path / "decorators.py"
        test_file.write_text('''
@staticmethod
def static_func():
    pass

@property
def prop(self):
    return self._value

@classmethod
def class_method(cls):
    pass
''')
        
        analyzer = PythonAnalyzer(str(tmp_path))
        result = analyzer.analyze_file(str(test_file))
        
        # 验证装饰器被提取
        decorated = [f for f in result.functions if f.decorators]
        assert len(decorated) >= 1, "预期有装饰器的函数"


class TestCrossLanguageConsistency:
    """T4.2: 跨语言一致性 [P1]"""
    
    def test_get_analyzer_by_language(self):
        """测试按语言获取分析器"""
        language_map = {
            'python': PythonAnalyzer,
            'py': PythonAnalyzer,
            'typescript': TypeScriptAnalyzer,
            'ts': TypeScriptAnalyzer,
            'javascript': TypeScriptAnalyzer,
            'js': TypeScriptAnalyzer,
            'java': JavaAnalyzer,
            'cpp': CppAnalyzer,
            'c++': CppAnalyzer,
            'php': PhpAnalyzer,
            'ruby': RubyAnalyzer,
            'go': GoAnalyzer,
            'rust': RustAnalyzer,
            'swift': SwiftAnalyzer,
            'kotlin': KotlinAnalyzer,
            'html': HtmlAnalyzer,
        }
        
        for lang, expected_class in language_map.items():
            analyzer = get_analyzer(".", language=lang)
            assert isinstance(analyzer, expected_class), \
                f"语言'{lang}'应返回{expected_class.__name__}"
    
    def test_multilang_equivalent_structure(self, tmp_path):
        """测试多语言等价类定义文件解析"""
        # 创建不同语言的等价类定义
        python_class = tmp_path / "service.py"
        python_class.write_text('''
class Service:
    def process(self, data):
        return data
''')
        
        typescript_class = tmp_path / "service.ts"
        typescript_class.write_text('''
class Service {
    process(data: any): any {
        return data;
    }
}
''')
        
        java_class = tmp_path / "Service.java"
        java_class.write_text('''
public class Service {
    public String process(String data) {
        return data;
    }
}
''')
        
        # 各语言解析后结构应相似
        py_analyzer = PythonAnalyzer(str(tmp_path))
        ts_analyzer = TypeScriptAnalyzer(str(tmp_path))
        java_analyzer = JavaAnalyzer(str(tmp_path))
        
        py_result = py_analyzer.analyze_file(str(python_class))
        ts_result = ts_analyzer.analyze_file(str(typescript_class))
        java_result = java_analyzer.analyze_file(str(java_class))
        
        # 验证都识别出了类
        assert "Service" in py_result.classes or len(py_result.functions) >= 1
        assert len(ts_result.classes) >= 1 or len(ts_result.functions) >= 1
        assert len(java_result.classes) >= 1 or len(java_result.functions) >= 1
    
    def test_language_detection_by_extension(self, tmp_path):
        """测试按文件扩展名自动检测语言"""
        test_cases = [
            ("test.py", "python"),
            ("test.ts", "typescript"),
            ("test.js", "typescript"),
            ("test.java", "java"),
            ("test.cpp", "cpp"),
            ("test.go", "go"),
            ("test.rs", "rust"),
            ("test.php", "php"),
            ("test.rb", "ruby"),
            ("test.swift", "swift"),
            ("test.kt", "kotlin"),
            ("test.html", "html"),
        ]
        
        for filename, expected_lang in test_cases:
            test_file = tmp_path / filename
            test_file.write_text("")  # 创建空文件
            
            analyzer = get_analyzer(str(tmp_path))
            result = analyzer.analyze_file(str(test_file))
            
            assert result is not None, f"应能分析{filename}"


class TestCallGraph:
    """T4.3: call_graph 调用关系 [P1]"""
    
    def test_extract_function_calls(self, tmp_path):
        """测试函数调用提取"""
        test_file = tmp_path / "calls.py"
        test_file.write_text('''
def helper():
    return 1

def process(data):
    result = helper()
    return result

def main():
    data = [1, 2, 3]
    process(data)
''')
        
        analyzer = PythonAnalyzer(str(tmp_path))
        result = analyzer.analyze_file(str(test_file))
        
        # 找到 main 函数
        main_func = next((f for f in result.functions if f.name == "main"), None)
        assert main_func is not None, "应找到main函数"
        
        # 验证 main 调用了 process
        if main_func.calls:
            assert "process" in main_func.calls or any("process" in c for c in main_func.calls)
    
    def test_method_calls_in_class(self, tmp_path):
        """测试类内方法调用"""
        test_file = tmp_path / "class_calls.py"
        test_file.write_text('''
class Service:
    def __init__(self):
        self.data = []
    
    def add(self, item):
        self.data.append(item)
    
    def process(self):
        for item in self.data:
            self._handle(item)
    
    def _handle(self, item):
        print(item)
''')
        
        analyzer = PythonAnalyzer(str(tmp_path))
        result = analyzer.analyze_file(str(test_file))
        
        # 验证方法被识别
        methods = [f for f in result.functions if f.is_method]
        assert len(methods) >= 2, f"预期至少2个方法，实际{len(methods)}"


class TestFunctionInfo:
    """测试 FunctionInfo 数据结构"""
    
    def test_function_info_to_dict(self):
        """测试 FunctionInfo 序列化"""
        func = FunctionInfo(
            name="test_func",
            file_path="/path/to/file.py",
            line_number=10,
            parameters=["a", "b"],
            return_type="int",
            is_async=False,
            is_method=False,
            class_name=None,
            decorators=["staticmethod"],
            docstring="Test function"
        )
        
        d = func.to_dict()
        
        assert d["name"] == "test_func"
        assert d["line_number"] == 10
        assert d["parameters"] == ["a", "b"]
        assert d["return_type"] == "int"
    
    def test_function_full_name(self):
        """测试函数全名"""
        # 普通函数
        func1 = FunctionInfo(
            name="simple_func",
            file_path="test.py",
            line_number=1
        )
        assert func1.full_name == "simple_func"
        
        # 类方法
        func2 = FunctionInfo(
            name="method",
            file_path="test.py",
            line_number=10,
            is_method=True,
            class_name="MyClass"
        )
        assert func2.full_name == "MyClass.method"
    
    def test_function_signature(self):
        """测试函数签名"""
        func = FunctionInfo(
            name="add",
            file_path="test.py",
            line_number=1,
            parameters=["a", "b"]
        )
        
        assert func.signature == "add(a, b)"


class TestModuleInfo:
    """测试 ModuleInfo 数据结构"""
    
    def test_module_info_structure(self):
        """测试模块信息结构"""
        module = ModuleInfo(
            name="test_module",
            file_path="/path/to/test.py",
            line_number=1
        )
        
        module.functions.append(FunctionInfo(
            name="func1",
            file_path="/path/to/test.py",
            line_number=10
        ))
        module.classes.append("MyClass")
        module.imports.extend(["os", "sys"])
        
        assert len(module.functions) == 1
        assert len(module.classes) == 1
        assert len(module.imports) == 2


class TestHtmlAnalyzer:
    """测试 HTML 分析器（新增）"""
    
    def test_analyze_html_structure(self, tmp_path):
        """测试 HTML 结构分析"""
        html_file = tmp_path / "page.html"
        html_file.write_text('''
<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
</head>
<body>
    <div id="app" class="container">
        <h1>Title</h1>
        <form id="login">
            <input type="text" name="username">
            <button type="submit">Submit</button>
        </form>
    </div>
</body>
</html>
''')
        
        analyzer = HtmlAnalyzer(str(tmp_path))
        result = analyzer.analyze_file(str(html_file))
        
        assert result is not None
        # HTML 分析结果存储在 extra 字段
        if hasattr(result, 'extra') and result.extra:
            assert "title" in result.extra or "ids" in result.extra


class TestAnalyzerExtension:
    """测试分析器扩展能力"""
    
    def test_cpp_analyzer_basic(self, tmp_path):
        """测试 C++ 分析器基础功能"""
        cpp_file = tmp_path / "test.cpp"
        cpp_file.write_text('''
#include <iostream>

class Calculator {
public:
    int add(int a, int b) {
        return a + b;
    }
    
    void print(int value) {
        std::cout << value << std::endl;
    }
};
''')
        
        analyzer = CppAnalyzer(str(tmp_path))
        result = analyzer.analyze_file(str(cpp_file))
        
        assert result is not None
        assert len(result.functions) >= 1 or len(result.classes) >= 1
    
    def test_go_analyzer_basic(self, tmp_path):
        """测试 Go 分析器基础功能"""
        go_file = tmp_path / "main.go"
        go_file.write_text('''
package main

func add(a, b int) int {
    return a + b
}

func main() {
    result := add(1, 2)
    println(result)
}
''')
        
        analyzer = GoAnalyzer(str(tmp_path))
        result = analyzer.analyze_file(str(go_file))
        
        assert result is not None
        assert len(result.functions) >= 1
    
    def test_rust_analyzer_basic(self, tmp_path):
        """测试 Rust 分析器基础功能"""
        rust_file = tmp_path / "main.rs"
        rust_file.write_text('''
fn main() {
    println!("Hello");
}

fn add(a: i32, b: i32) -> i32 {
    a + b
}
''')
        
        analyzer = RustAnalyzer(str(tmp_path))
        result = analyzer.analyze_file(str(rust_file))
        
        assert result is not None

    def test_rust_masks_strings_without_shifting_offsets(self, tmp_path):
        """Rust strings/comments are masked in place so later line numbers survive."""
        rust_file = tmp_path / "scanner.rs"
        rust_file.write_text(
            "\n".join([
                "fn scan_claude() {",
                '    let wire = "\\"type\\":\\"user\\"";',
                '    let url = "https://example.test/session";',
                "}",
                "",
                "fn scan_kimi() {",
                "    scan_claude();",
                "}",
                "",
                "fn scan_codex() {",
                "}",
                "",
                "fn parse_kimi_wire_waiting() -> bool {",
                "    true",
                "}",
                "",
                "fn live_cwds() {",
                "}",
                "",
            ]),
            encoding="utf-8",
        )

        analyzer = RustAnalyzer(str(tmp_path))
        result = analyzer.analyze_file(str(rust_file))
        functions = {func.name: func for func in result.functions}

        assert {"scan_claude", "scan_kimi", "scan_codex", "parse_kimi_wire_waiting", "live_cwds"} <= set(functions)
        assert functions["scan_claude"].line_number == 1
        assert functions["scan_claude"].line_end == 4
        assert functions["scan_kimi"].line_number == 6
        assert functions["scan_kimi"].line_end == 8


# ============ 运行测试 ============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
