"""CodeDendrite - 基于 AST 的代码因果导航系统。

公开接口全部经由 serve/ 层导出，与源码实现解耦：

    from CodeDendrite import scan_project, analyze_code, search_symbol
    from CodeDendrite import list_all_symbols, list_anchors, create_anchor
    from CodeDendrite import find_subclasses, analyze_super_calls, build_override_chain
    from CodeDendrite import analyze_call_chain, trace_variable, generate_dataflow_html
    from CodeDendrite import ContextBuilder, SymbolExpander
    from CodeDendrite import PathTracer, NodeReplacer
    from CodeDendrite import AnchorMemory, Observation

实现分布在 base / parse / index / relate / synth / view / serve 七层，
新代码应直接 import 归属层（例如 `from index.api.anchors import load_anchors`），
本文件只为外部调用方保留稳定的顶层入口。
"""

import sys as _sys
from pathlib import Path as _Path

# 七个桶是本目录下的顶层包，作为库被 import 时需要让它们可见
_ROOT = str(_Path(__file__).parent)
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

from serve import *              # noqa: F401,F403,E402
from serve import __all__ as _SERVE_ALL   # noqa: E402

__all__ = list(_SERVE_ALL)

# ─── 可选模块：不在 serve/api 的导出清单里，各自包自带 __all__ ───
# 三条都是可选能力，装不上就不进 __all__，不影响主干 import。

try:
    from synth.context_builder import ContextBuilder, SymbolExpander  # noqa: F401,E402
    __all__ += ["ContextBuilder", "SymbolExpander"]
except ImportError:
    pass

try:
    from relate.pathTracer import PathTracer, NodeReplacer  # noqa: F401,E402
    __all__ += ["PathTracer", "NodeReplacer"]
except ImportError:
    pass

try:
    from synth.anchorMemory import AnchorMemory, Observation  # noqa: F401,E402
    __all__ += ["AnchorMemory", "Observation"]
except ImportError:
    pass

