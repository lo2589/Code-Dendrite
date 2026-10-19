"""
override_analyzer.py - Python 方法覆盖分析器
==============================================
从 TypeScript 迁移的 Python 方法覆盖分析工具。

功能：
- 分析方法在继承链中的覆盖情况
- 构建方法覆盖链
- 检测抽象方法的实现
- 支持 @override 装饰器

用法：
    from analyzer.inherit.language.python.override_analyzer import (
        build_override_chain,
        find_overridden_method,
        find_abstract_implementations
    )

    overrides = build_override_chain(chain, "my_method")
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set

from analyzer.inherit.language.python.override_analyzer.override_chain import OverrideInfo, build_override_chain, OverrideAnalyzer, OverrideChain, detect_override_decorator, find_abstract_implementations, find_overridden_method, get_override_depth
from analyzer.inherit.language.python.override_analyzer.validate_overrides import validate_overrides

__all__ = ['OverrideInfo', 'build_override_chain', 'OverrideAnalyzer', 'OverrideChain', 'detect_override_decorator', 'find_abstract_implementations', 'find_overridden_method', 'get_override_depth', 'validate_overrides']
