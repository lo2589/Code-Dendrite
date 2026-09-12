"""CodeDendrite usage 层。

任务包、工作流、工具面、CLI、自愈——"怎么用起来"都在这层。
对外公开的 API 出口在 ``api`` 层，不在这里；这里不再转发 ``api``，
否则 ``import api`` 会因为 ``api.analysis → view → usage → api`` 形成环。
"""

import sys as _sys
from pathlib import Path as _Path

# 五层是本目录下的顶层包，作为库被 import 时需要让它们可见
_ROOT = str(_Path(__file__).resolve().parent.parent)
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)
