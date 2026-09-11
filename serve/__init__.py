"""
CodeDendrite 服务层
==================
对外公开接口的唯一出口。真正的导出清单在 ``serve/api/__init__.py``，
这里原样再导出一遍，好让 ``import serve`` 与 ``import serve.api`` 等价：

    from serve import scan_project, analyze_code, search_symbol

七个桶（base / parse / index / relate / synth / view / serve）是本目录下的
顶层包，被当作库 import 时需要让它们可见。
"""

import sys as _sys
from pathlib import Path as _Path

# 本文件在 <repo>/serve/ 下，仓库根是桶所在的目录
_ROOT = str(_Path(__file__).resolve().parent.parent)
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

from serve.api import *          # noqa: F401,F403,E402
from serve.api import __all__    # noqa: F401,E402
