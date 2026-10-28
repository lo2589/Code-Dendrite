"""已整包搬到 analyzer.repair（锚点修复属于锚点身份那一层）。这里只转发给外部代码。

搬家原因：analyzer 生成锚点时要调修复，只能在函数里反向 import usage.repair——
分层就不是单向的。repair 本身只依赖 analyzer，搬下去以后依赖只剩一个方向。
仓库里的引用已经全部改成 analyzer.repair；这里把包和每个子模块都指向新位置。
"""
import importlib
import pkgutil
import sys

_NEW = "analyzer.repair"
_pkg = importlib.import_module(_NEW)
sys.modules[__name__] = _pkg
for _info in pkgutil.walk_packages(_pkg.__path__, _NEW + "."):
    sys.modules[__name__ + _info.name[len(_NEW):]] = importlib.import_module(_info.name)
