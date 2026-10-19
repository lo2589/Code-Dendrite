"""
code_map.py - Interactive Code Map (D3.js Treemap)
===================================================
Generates an interactive HTML treemap showing the project structure.
Modules are rectangles sized by symbol count, colored by edge frequency (hotspot).

Features:
  - Treemap layout: modules as rectangles, sized by symbol count
  - Heat coloring: cold (blue) to hot (red) based on total edge count
  - Click module to expand and show internal functions
  - Hover tooltip: module name, symbol count, edge count
  - Zoom/pan support
  - Click function to link to relation graph

Usage:
  python code_map.py <project_root> [--output codemap.html]
"""

import json
import argparse
from pathlib import Path
from typing import Optional
from collections import defaultdict


IGNORE_PATH_PARTS = {"__pycache__"}
IGNORE_PREFIXES = (".tmp_",)

from view.code_map.build_treemap_data import _build_treemap_data, _should_skip_file

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

    anchors = {
        node_id: anchor
        for node_id, anchor in anchors.items()
        if not _should_skip_file(anchor.get("file", ""))
    }
    relations["edges"] = [
        edge for edge in relations.get("edges", [])
        if edge.get("from_id") in anchors and edge.get("to_id") in anchors
    ]

    return anchors, relations

def _html_template(tree_json: str, title: str, max_edges: int) -> str:
    """Generate HTML with D3.js treemap."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: #0d1117;
  color: #e6edf3;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace;
  overflow: hidden;
}}
#treemap {{
  width: 100vw;
  height: 100vh;
}}
#breadcrumb {{
  position: fixed;
  top: 12px; left: 12px;
  z-index: 10;
  background: rgba(22, 27, 34, 0.95);
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 8px 14px;
  font-size: 12px;
  backdrop-filter: blur(8px);
  display: flex;
  gap: 6px;
  align-items: center;
}}
#breadcrumb .crumb {{
  color: #58a6ff;
  cursor: pointer;
}}
#breadcrumb .crumb:hover {{ text-decoration: underline; }}
#breadcrumb .sep {{ color: #484f58; }}
#tooltip {{
  position: fixed;
  display: none;
  background: rgba(22, 27, 34, 0.97);
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 10px 14px;
  font-size: 11px;
  z-index: 20;
  max-width: 300px;
  pointer-events: none;
  line-height: 1.6;
  backdrop-filter: blur(8px);
}}
#legend {{
  position: fixed;
  bottom: 12px; right: 12px;
  z-index: 10;
  background: rgba(22, 27, 34, 0.95);
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 11px;
  backdrop-filter: blur(8px);
}}
#legend .bar {{
  width: 200px;
  height: 14px;
  border-radius: 3px;
  margin: 6px 0;
  background: linear-gradient(to right, #1f6feb, #3fb950, #d29922, #f85149);
}}
#legend .labels {{
  display: flex;
  justify-content: space-between;
  color: #848d97;
  font-size: 10px;
}}
#stats {{
  position: fixed;
  top: 12px; right: 12px;
  z-index: 10;
  background: rgba(22, 27, 34, 0.95);
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 11px;
  backdrop-filter: blur(8px);
}}
#stats span {{ color: #58a6ff; font-weight: 600; }}
</style>
</head>
<body>

<div id="treemap"></div>
<div id="breadcrumb"><span class="crumb" onclick="zoomOut()">project</span></div>
<div id="tooltip"></div>
<div id="legend">
  <div>边连接热度</div>
  <div class="bar"></div>
  <div class="labels"><span>低</span><span>高</span></div>
</div>
<div id="stats"></div>

<script>
const treeData = {tree_json};
const maxEdges = {max_edges};

const width = window.innerWidth;
const height = window.innerHeight;

const color = d3.scaleSequential()
  .domain([0, Math.max(maxEdges, 1)])
  .interpolator(d3.interpolateRgb('#161b22', '#58a6ff'));

const tooltip = document.getElementById('tooltip');

const root = d3.hierarchy(treeData)
  .sum(d => d.value || d.symbol_count || 1)
  .sort((a, b) => b.value - a.value);

const treemap = d3.treemap()
  .size([width, height])
  .padding(2)
  .paddingTop(20)
  .round(true);

treemap(root);

const svg = d3.select('#treemap')
  .append('svg')
  .attr('width', width)
  .attr('height', height);

let currentRoot = root;
let breadcrumbs = [root];

function render(node) {{
  currentRoot = node;
  treemap(node);
  svg.selectAll('*').remove();

  const leaves = node.descendants().filter(d => d.depth === node.depth + 1 || (!d.children && d.depth > node.depth));

  // Group headers (module names)
  const groups = node.children || [];
  groups.forEach(g => {{
    svg.append('text')
      .attr('x', g.x0 + 4)
      .attr('y', g.y0 + 14)
      .text(g.data.name)
      .attr('fill', '#848d97')
      .attr('font-size', '11px')
      .attr('font-weight', '600')
      .attr('pointer-events', 'none');
  }});

  // Leaf rectangles
  const cells = svg.selectAll('.cell')
    .data(leaves)
    .enter()
    .append('g')
    .attr('class', 'cell');

  cells.append('rect')
    .attr('x', d => d.x0)
    .attr('y', d => d.y0)
    .attr('width', d => Math.max(0, d.x1 - d.x0))
    .attr('height', d => Math.max(0, d.y1 - d.y0))
    .attr('fill', d => {{
      const edges = d.data.edge_count || d.data.edges || 0;
      return color(edges);
    }})
    .attr('stroke', '#30363d')
    .attr('stroke-width', 0.5)
    .attr('rx', 2)
    .attr('cursor', d => d.children ? 'pointer' : 'default')
    .on('click', function(event, d) {{
      if (d.children) {{
        breadcrumbs.push(d);
        updateBreadcrumb();
        render(d);
      }}
    }})
    .on('mouseover', function(event, d) {{
      d3.select(this).attr('stroke', '#58a6ff').attr('stroke-width', 2);
      let html = '<strong style="color:#58a6ff">' + d.data.name + '</strong>';
      if (d.data.full_path) html += '<br><span style="color:#848d97">' + d.data.full_path + '</span>';
      if (d.data.symbol_count !== undefined) html += '<br>Symbols: ' + d.data.symbol_count;
      if (d.data.edge_count !== undefined) html += '<br>Edges: ' + d.data.edge_count;
      if (d.data.edges !== undefined) html += '<br>Edges: ' + d.data.edges;
      if (d.data.type) html += '<br>Type: ' + d.data.type;
      if (d.data.line) html += '<br>Line: ' + d.data.line;
      tooltip.innerHTML = html;
      tooltip.style.display = 'block';
    }})
    .on('mousemove', function(event) {{
      tooltip.style.left = (event.clientX + 15) + 'px';
      tooltip.style.top = (event.clientY + 15) + 'px';
    }})
    .on('mouseout', function() {{
      d3.select(this).attr('stroke', '#30363d').attr('stroke-width', 0.5);
      tooltip.style.display = 'none';
    }});

  // Labels
  cells.append('text')
    .attr('x', d => d.x0 + 3)
    .attr('y', d => d.y0 + 12)
    .text(d => {{
      const w = d.x1 - d.x0;
      if (w < 30) return '';
      const name = d.data.name || '';
      return w < 80 ? name.slice(0, 8) : name;
    }})
    .attr('fill', '#e6edf3')
    .attr('font-size', '9px')
    .attr('pointer-events', 'none');

  // Stats
  const totalSymbols = leaves.reduce((s, d) => s + (d.data.symbol_count || 1), 0);
  document.getElementById('stats').innerHTML =
    '模块: <span>' + groups.length + '</span> | ' +
    '项目: <span>' + leaves.length + '</span>';
}}

function updateBreadcrumb() {{
  const bc = document.getElementById('breadcrumb');
  bc.innerHTML = '';
  breadcrumbs.forEach((b, i) => {{
    if (i > 0) {{
      const sep = document.createElement('span');
      sep.className = 'sep';
      sep.textContent = ' > ';
      bc.appendChild(sep);
    }}
    const crumb = document.createElement('span');
    crumb.className = 'crumb';
    crumb.textContent = b.data.name;
    crumb.onclick = function() {{
      breadcrumbs = breadcrumbs.slice(0, i + 1);
      updateBreadcrumb();
      render(b);
    }};
    bc.appendChild(crumb);
  }});
}}

function zoomOut() {{
  breadcrumbs = [root];
  updateBreadcrumb();
  render(root);
}}

render(root);
</script>
</body>
</html>'''

def generate_code_map(root: str, output: Optional[str] = None) -> str:
    """
    Generate an interactive D3.js treemap code map HTML.

    Args:
        root: Project root directory
        output: Output HTML path (default: <root>/.codedendrite/code_map.html)

    Returns:
        Path to the generated HTML file
    """
    anchors, relations = _load_data(root)
    tree_data = _build_treemap_data(anchors, relations)

    # Compute max edge count for color scale
    node_edges = defaultdict(int)
    for e in relations.get("edges", []):
        node_edges[e["from_id"]] += 1
        node_edges[e["to_id"]] += 1
    max_edges = max(node_edges.values()) if node_edges else 1

    if not output:
        output = str(Path(root) / ".codedendrite" / "code_map.html")

    tree_json = json.dumps(tree_data, ensure_ascii=False)
    title = f"CodeDendrite Code Map - {Path(root).name}"
    html = _html_template(tree_json, title, max_edges)

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(html, encoding="utf-8")

    total_files = sum(len(m.get("children", [])) for m in tree_data.get("children", []))
    total_modules = len(tree_data.get("children", []))
    print(f"code_map: {output} ({total_modules} modules, {total_files} files)")
    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate interactive code map")
    parser.add_argument("root", help="Project root directory")
    parser.add_argument("--output", default=None, help="Output HTML path")
    args = parser.parse_args()

    generate_code_map(args.root, args.output)
