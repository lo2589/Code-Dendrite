"""已搬到 scanner.shared.formula_skip。这里只转发：旧模块名指向同一个模块对象。

搬家原因：下层要用它，却只能在函数里反向 import 上层——分层就不是单向的。
"""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("scanner.shared.formula_skip")
