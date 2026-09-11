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

from view.visualize.call_timeline.generate_mermaid import _build_call_adj, _find_entry, _generate_mermaid, _short_name, _trace_calls

def _load_data(root: str):
    """Load anchors.json and relations.json."""
    root = Path(root)
    anchors_path = root / ".codedendrite" / "anchors.json"
    relations_path = root / ".codedendrite" / "relations.json"

    anchors = {}
    if anchors_path.exists():
        anchors = json.loads(anchors_path.read_text(encoding="utf-8"))

    relations = {"edges": []}
    if relations_path.exists():
        relations = json.loads(relations_path.read_text(encoding="utf-8"))

    return anchors, relations

def _html_template(mermaid_text: str, title: str, entry: str, raw_mermaid: str) -> str:
    """Generate HTML with Mermaid CDN renderer."""
    # Escape for embedding in JS
    mermaid_escaped = mermaid_text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: #0d1117;
  color: #e6edf3;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace;
  padding: 20px;
  overflow: auto;
}}
h1 {{
  font-size: 16px;
  color: #58a6ff;
  margin-bottom: 6px;
}}
.subtitle {{
  font-size: 12px;
  color: #848d97;
  margin-bottom: 20px;
}}
#diagram {{
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 20px;
  overflow-x: auto;
  min-height: 200px;
}}
.mermaid {{
  text-align: center;
}}
#raw-toggle {{
  margin-top: 16px;
  display: flex;
  gap: 10px;
  align-items: center;
}}
#raw-toggle button {{
  background: #21262d;
  border: 1px solid #30363d;
  color: #e6edf3;
  padding: 6px 14px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}}
#raw-toggle button:hover {{ background: #30363d; }}
#raw-code {{
  display: none;
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 14px;
  margin-top: 10px;
  font-size: 11px;
  white-space: pre-wrap;
  color: #848d97;
  max-height: 400px;
  overflow: auto;
}}
</style>
</head>
<body>

<h1>Call Chain Timeline</h1>
<div class="subtitle">Entry: {entry}</div>

<div id="diagram">
  <pre class="mermaid">
{raw_mermaid}
  </pre>
</div>

<div id="raw-toggle">
  <button onclick="toggleRaw()">Show/Hide Mermaid Source</button>
</div>
<pre id="raw-code">{raw_mermaid}</pre>

<script>
  mermaid.initialize({{
    startOnLoad: true,
    theme: 'base',
    securityLevel: 'loose',
    themeVariables: {{
      primaryColor: '#161b22',
      primaryTextColor: '#e6edf3',
      primaryBorderColor: '#30363d',
      lineColor: '#58a6ff',
      signalColor: '#58a6ff',
      signalTextColor: '#e6edf3',
      actorBkg: '#161b22',
      actorBorder: '#30363d',
      actorTextColor: '#e6edf3',
      noteBkgColor: '#1f2937',
      noteBorderColor: '#30363d',
      noteTextColor: '#e6edf3',
    }},
    sequence: {{
      diagramMarginX: 20,
      diagramMarginY: 20,
      actorMargin: 60,
      width: 150,
      height: 40,
      noteMargin: 10,
      messageMargin: 40,
      mirrorActors: false,
      useMaxWidth: false,
    }}
  }});

  function toggleRaw() {{
    const el = document.getElementById('raw-code');
    el.style.display = el.style.display === 'none' ? 'block' : 'none';
  }}
</script>
</body>
</html>'''

def generate_call_timeline(
    root: str,
    entry_symbol: str,
    output: Optional[str] = None,
    max_depth: int = 5,
    error_symbol: Optional[str] = None,
) -> str:
    """
    Generate a Mermaid sequenceDiagram call timeline HTML.

    Args:
        root: Project root directory
        entry_symbol: Entry function symbol or node_id
        output: Output HTML path (default: <root>/.codedendrite/call_timeline.html)
        max_depth: Maximum call chain depth
        error_symbol: Optional symbol to highlight as error point

    Returns:
        Path to the generated HTML file
    """
    anchors, relations = _load_data(root)
    adj, edge_data = _build_call_adj(relations)

    entry = _find_entry(entry_symbol, anchors, adj)
    calls = _trace_calls(entry, adj, edge_data, max_depth)

    mermaid_text = _generate_mermaid(calls, error_symbol)

    if not output:
        output = str(Path(root) / ".codedendrite" / "call_timeline.html")

    title = f"CodeDendrite Timeline - {_short_name(entry)}"
    html = _html_template(mermaid_text, title, entry, mermaid_text)

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(html, encoding="utf-8")
    print(f"call_timeline: {output} ({len(calls)} calls, depth={max_depth})")
    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate call chain timeline")
    parser.add_argument("root", help="Project root directory")
    parser.add_argument("entry", help="Entry symbol or node_id")
    parser.add_argument("--depth", type=int, default=5, help="Max call depth")
    parser.add_argument("--error", default=None, help="Error symbol to highlight")
    parser.add_argument("--output", default=None, help="Output HTML path")
    args = parser.parse_args()

    generate_call_timeline(args.root, args.entry, args.output, args.depth, args.error)
