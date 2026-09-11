"""  
CodeDendrite - 代码理解工具库

使用示例:
    from serve.api import scan_project, analyze_code, search_symbol
    
    # 扫描项目
    result = scan_project("/path/to/project")
    
    # 分析代码
    analysis = analyze_code("src/main.py")
    
    # 搜索符号
    matches = search_symbol("my_function")
    
    # 锚点管理
    from serve.api import list_all_symbols, list_anchors, create_anchor
    
    # 继承分析
    from serve.api import find_subclasses, analyze_super_calls, build_override_chain
    
    # 数据流分析
    from serve.api import analyze_call_chain, trace_variable, generate_dataflow_html
    
    # NEW: 上下文构建器（压缩地图）
    from synth.context_builder import ContextBuilder, SymbolExpander
    
    # NEW: 路径追踪
    from relate.pathTracer import PathTracer, NodeReplacer
    
    # NEW: 锚点记忆
    from synth.anchorMemory import AnchorMemory, Observation
"""

# ─── 自动路径配置（解决 ModuleNotFoundError）───
import sys
from pathlib import Path

# 将 CodeDendrite 目录加入 sys.path，使 `from api import *` 能正常工作
_CODEDENDRITE_DIR = str(Path(__file__).parent)
if _CODEDENDRITE_DIR not in sys.path:
    sys.path.insert(0, _CODEDENDRITE_DIR)

# 所有公开接口统一从 api/ 层导入，与源码实现完全解耦
from serve.api import *  # noqa: F401,F403
from serve.api import __all__  # noqa: F401

# ─── 上下文构建器 ───
try:
    from synth.context_builder import ContextBuilder, SymbolExpander, format_map
except ImportError:
    pass  # 可选模块

# ─── 路径追踪 ───
try:
    from relate.pathTracer import PathTracer, PipelineNode, NodeReplacer, check_compatibility
except ImportError:
    pass  # 可选模块

# ─── 锚点记忆 ───
try:
    from synth.anchorMemory import AnchorMemory, MemoryEntry, Milestone, Observation, RiskLevel
except ImportError:
    pass  # 可选模块

# 可选模块导入成功的名字并入 __all__，使 `from serve import *` 能带出它们
__all__ = list(__all__) + [
    _n for _n in (
        "ContextBuilder", "SymbolExpander", "format_map",
        "PathTracer", "PipelineNode", "NodeReplacer", "check_compatibility",
        "AnchorMemory", "MemoryEntry", "Milestone", "Observation", "RiskLevel",
    )
    if _n in globals() and _n not in __all__
]
