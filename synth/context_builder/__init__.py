"""
context_builder — 将项目锚点压缩成 AI 可用的上下文地图

核心理念：
  存储层（anchor JSON）是为检索设计的，五万行无法直接喂给 AI。
  context_builder 将其压缩为 200-500 行的"导航地图"，
  AI 需要某个符号的具体实现时，再通过 expand() 精准取出。

用法：
  from synth.context_builder import ContextBuilder

  cb = ContextBuilder(project_root="/path/to/project")
  map_text = cb.build_map(budget_tokens=2000)
  code = cb.expand("validate_user")
"""

from synth.context_builder.builder import ContextBuilder
from synth.context_builder.formatter import format_map
from synth.context_builder.expander import SymbolExpander

__all__ = ["ContextBuilder", "format_map", "SymbolExpander"]
