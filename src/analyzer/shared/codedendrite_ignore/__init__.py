"""已搬到 scanner.shared.codedendrite_ignore（扫描层）。这里只转发，包和两个子模块都指向新位置。"""
import importlib
import sys

_new = "scanner.shared.codedendrite_ignore"
for _sub in ("", ".code_dendrite_ignore", ".glob_match"):
    sys.modules[__name__ + _sub] = importlib.import_module(_new + _sub)
