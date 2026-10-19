"""
query.py — CodeDendrite 查询 CLI
================================
用法:
    python api/query.py edges <keyword>          # 过滤边
    python api/query.py count                    # 统计边类型
    python api/query.py expand <node_id>         # 展开节点
    python api/query.py anchors <keyword>        # 过滤锚点
    python api/query.py fileanchors <file>       # 列出单个文件内的 anchors
    python api/query.py graph [focus] [radius]   # 生成交互式关系图
    python api/query.py timeline <entry> [depth]  # 生成调用链时间线
    python api/query.py codemap                  # 生成代码地图
"""
import sys
import os

from api.query.rank_anchor_matches import _rank_anchor_matches
from api.query.cmd_chain import _ensure_path, cmd_edges, cmd_count, cmd_expand, cmd_anchors, cmd_fileanchors, cmd_map, cmd_graph, cmd_timeline, cmd_codemap, cmd_chain, cmd_registered

__all__ = ['_rank_anchor_matches', '_ensure_path', 'cmd_edges', 'cmd_count', 'cmd_expand', 'cmd_anchors', 'cmd_fileanchors', 'cmd_map', 'cmd_graph', 'cmd_timeline', 'cmd_codemap', 'cmd_chain', 'cmd_registered']
