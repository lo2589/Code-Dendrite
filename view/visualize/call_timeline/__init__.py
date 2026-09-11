"""
call_timeline.py - Call Chain Timeline (Mermaid sequenceDiagram)
================================================================
Given an entry function, traces its call chain and generates a
Mermaid sequenceDiagram with parameter annotations and error highlighting.

Features:
  - Vertical timeline of function calls from entry point
  - Parameter annotations on arrows (data_in/data_out)
  - Error point highlighting (red note on error_symbol)
  - Depth control (max call depth)
  - Participant grouping by module/file

Usage:
  python call_timeline.py <project_root> <entry_symbol> [--depth 5] [--error symbol] [--output timeline.html]
"""

import json
import argparse
from pathlib import Path
from typing import Optional
from collections import defaultdict

from view.visualize.call_timeline.generate_mermaid import _build_call_adj, _find_entry, _short_name, _safe_alias, _get_module, _generate_mermaid, _trace_calls
from view.visualize.call_timeline.generate_call_timeline import _load_data, _html_template, generate_call_timeline

__all__ = ['_build_call_adj', '_find_entry', '_short_name', '_safe_alias', '_get_module', '_generate_mermaid', '_trace_calls', '_load_data', '_html_template', 'generate_call_timeline']
