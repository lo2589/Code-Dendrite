"""  
CodeDendrite - 代码理解工具库

使用示例:
    from tools.CodeDendrite import scan_project, analyze_code, search_symbol
    
    # 扫描项目
    result = scan_project("/path/to/project")
    
    # 分析代码
    analysis = analyze_code("src/main.py")
    
    # 搜索符号
    matches = search_symbol("my_function")
    
    # 锚点管理
    from tools.CodeDendrite import list_all_symbols, list_anchors, create_anchor
    
    # 继承分析
    from tools.CodeDendrite import find_subclasses, analyze_super_calls, build_override_chain
    
    # 数据流分析
    from tools.CodeDendrite import analyze_call_chain, trace_variable, generate_dataflow_html
    
    # NEW: 上下文构建器（压缩地图）
    from tools.CodeDendrite import build_context, expand_symbol
    
    # NEW: 路径追踪
    from tools.CodeDendrite import PathTracer, trace_path, replace_node
    
    # NEW: 锚点记忆
    from tools.CodeDendrite import AnchorMemory, record_observation
"""

# ─── 自动路径配置（解决 ModuleNotFoundError）───
import sys
from pathlib import Path

# 将 CodeDendrite 目录加入 sys.path，使 `from api import *` 能正常工作
_CODEDENDRITE_DIR = str(Path(__file__).parent)
if _CODEDENDRITE_DIR not in sys.path:
    sys.path.insert(0, _CODEDENDRITE_DIR)

# 所有公开接口统一从 api/ 层导入，与源码实现完全解耦
from api import *  # noqa: F401,F403
from api import __all__  # noqa: F401

# ─── NEW: 上下文构建器 ───
try:
    from context_builder.builder import build_context
    from context_builder.expander import expand_symbol
    from context_builder.formatter import format_context
except ImportError:
    pass  # 可选模块

# ─── NEW: 路径追踪 ───
try:
    from pathTracer.tracer import PathTracer, trace_path
    from pathTracer.replacer import replace_node
    from pathTracer.compatibility import check_compatibility
except ImportError:
    pass  # 可选模块

# ─── NEW: 锚点记忆 ───
try:
    from anchorMemory.memory import AnchorMemory, record_observation
    from anchorMemory.types import MemoryEntry, Milestone, Observation
except ImportError:
    pass  # 可选模块

# ─── NEW: 调用图补全 ───
try:
    from codeGenome.calls_extractor import CallsExtractor
except ImportError:
    pass  # 可选模块

# ─── NEW: 智能分析器 V2 ───
try:
    from smartAnalyzer.smart_analyzer_patch import SmartCodeAnalyzerV2
except ImportError:
    pass  # 可选模块
