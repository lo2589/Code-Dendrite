"""已搬到 scanner.shared.genome_identity（扫描层）。这里只转发：旧模块名指向同一个模块对象，analyzer 里的引用不用改。

搬家原因：scanner 产出这些东西，却要反向 import analyzer 才拿得到——分层从此不是单向的。
"""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("scanner.shared.genome_identity")
