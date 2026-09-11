"""
L3_Inheritance 单元测试
=======================
测试继承链追踪系统。
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from relate.inheritance import (
    parse_python_file,
    build_class_index,
    resolve_inheritance,
    resolve_external_class,
    get_builtin_class_info,
    get_site_packages_paths,
    compute_mro,
    find_method_origin,
    ClassIndex
)
from base.inheritance.types import ClassInfo, MethodInfo, ImportInfo


class TestParsePythonFile:
    """测试Python文件解析"""
    
    def test_parse_simple_class(self, tmp_path):
        """测试解析简单类"""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
class Animal:
    def speak(self):
        pass

class Dog(Animal):
    def speak(self):
        return "Woof"
""")
        
        result = parse_python_file(str(test_file))
        
        assert len(result.classes) == 2
        assert result.classes[0].name == "Animal"
        assert result.classes[1].name == "Dog"
        assert result.classes[1].bases == ["Animal"]
    
    def test_parse_imports(self, tmp_path):
        """测试解析导入语句"""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
import os
import sys as system
from typing import List, Dict as Dictionary
""")
        
        result = parse_python_file(str(test_file))
        
        assert len(result.imports) == 3
    
    def test_parse_methods(self, tmp_path):
        """测试解析方法"""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
class Calculator:
    def add(self, a, b):
        return a + b
    
    @staticmethod
    def multiply(a, b):
        return a * b
""")
        
        result = parse_python_file(str(test_file))
        
        assert len(result.classes) == 1
        assert len(result.classes[0].methods) == 2
        assert result.classes[0].methods[0].name == "add"
        assert result.classes[0].methods[1].name == "multiply"
    
    def test_parse_nonexistent_file(self):
        """测试解析不存在的文件"""
        result = parse_python_file("/nonexistent/file.py")
        
        assert result.classes == []
        assert result.imports == []
    
    def test_parse_decorators(self, tmp_path):
        """测试解析装饰器"""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
from dataclasses import dataclass

@dataclass
class Person:
    name: str
    age: int
""")
        
        result = parse_python_file(str(test_file))
        
        assert len(result.classes) == 1
        assert "dataclass" in str(result.classes[0].decorators)


class TestBuildClassIndex:
    """测试类索引构建"""
    
    def test_build_index(self, tmp_path):
        """测试构建类索引"""
        # 创建多个Python文件
        (tmp_path / "animal.py").write_text("class Animal: pass")
        (tmp_path / "dog.py").write_text("from animal import Animal\nclass Dog(Animal): pass")
        
        index = build_class_index(str(tmp_path))
        
        assert isinstance(index, ClassIndex)
        assert "Animal" in index.classes
        assert "Dog" in index.classes
        assert index.classes["Dog"].bases == ["Animal"]


class TestGetBuiltinClassInfo:
    """测试内置类信息获取"""
    
    def test_object_class(self):
        """测试object类"""
        result = get_builtin_class_info("object")
        
        assert result is not None
        assert result.name == "object"
        assert result.module == "builtins"
        assert result.bases == []
    
    def test_exception_class(self):
        """测试Exception类"""
        result = get_builtin_class_info("Exception")
        
        assert result is not None
        assert result.name == "Exception"
        assert result.module == "builtins"
        assert "BaseException" in result.bases
    
    def test_abc_class(self):
        """测试ABC类"""
        result = get_builtin_class_info("ABC")
        
        assert result is not None
        assert result.module == "abc"
    
    def test_nonexistent_class(self):
        """测试不存在的类"""
        result = get_builtin_class_info("NonExistentClass")
        
        assert result is None


class TestResolveInheritance:
    """测试继承链解析"""
    
    def test_resolve_simple_inheritance(self, tmp_path):
        """测试简单继承"""
        (tmp_path / "base.py").write_text("class Base: pass")
        (tmp_path / "derived.py").write_text("from base import Base\nclass Derived(Base): pass")
        
        index = build_class_index(str(tmp_path))
        chain = resolve_inheritance("Derived", index)
        
        assert len(chain) >= 1
        assert chain[0].name == "Derived"
    
    def test_resolve_builtin_inheritance(self):
        """测试内置类继承"""
        # 创建临时索引
        index = ClassIndex()
        # 添加一个继承自object的类
        from base.inheritance.types import ClassEntry
        index.classes["MyClass"] = ClassEntry(
            name="MyClass",
            file="test.py",
            line=1,
            bases=["object"],
            methods=[],
            imports=[],
            depth=0,
            is_external=False
        )
        
        chain = resolve_inheritance("MyClass", index)
        
        assert len(chain) >= 1


class TestGetSitePackagesPaths:
    """测试site-packages路径获取"""
    
    def test_returns_list(self):
        """测试返回列表"""
        result = get_site_packages_paths()
        
        assert isinstance(result, list)


class TestComputeMRO:
    """测试MRO计算"""
    
    def test_single_inheritance_mro(self, tmp_path):
        """测试单继承MRO"""
        (tmp_path / "a.py").write_text("class A: pass")
        (tmp_path / "b.py").write_text("from a import A\nclass B(A): pass")
        (tmp_path / "c.py").write_text("from b import B\nclass C(B): pass")
        
        index = build_class_index(str(tmp_path))
        mro = compute_mro("C", index)
        
        assert "C" in mro


class TestFindMethodOrigin:
    """测试方法定位"""
    
    def test_find_own_method(self, tmp_path):
        """测试查找自己定义的方法"""
        (tmp_path / "test.py").write_text("""
class Animal:
    def speak(self):
        pass
""")
        
        index = build_class_index(str(tmp_path))
        result = find_method_origin("Animal", "speak", index)
        
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
