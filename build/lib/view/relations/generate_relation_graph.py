"""
relation_graph.py - Interactive Relation Graph (Cytoscape.js)
=============================================================
Generates a standalone HTML file with an interactive code relation graph.

Features:
  - Nodes colored by module (file path grouping)
  - Edge colors by type: call/inherit/dataflow/impact/dispatch
  - Click node to expand/collapse neighbors
  - Search box with highlight
  - Drag to reposition nodes (cose layout)
  - Hover tooltip: symbol name, file:line, inputs/outputs
  - Legend panel showing edge type colors
  - Filter checkboxes per edge type

Usage:
  python relation_graph.py <project_root> [--focus node_id] [--radius 2] [--output graph.html]
"""

import json
import argparse
import hashlib
from pathlib import Path
from typing import Optional
from collections import defaultdict


EDGE_COLORS = {
    "call": "#58a6ff",
    "inherit": "#3fb950",
    "dataflow": "#bc8cff",
    "impact": "#f85149",
    "dispatch": "#d29922",
}

MODULE_COLORS = [
    "#264653", "#2a9d8f", "#e9c46a", "#f4a261", "#e76f51",
    "#606c38", "#283618", "#dda15e", "#bc6c25", "#023047",
    "#219ebc", "#8ecae6", "#6d6875", "#b5838d", "#ffb4a2",
    "#588157", "#3a5a40", "#a3b18a", "#344e41", "#dad7cd",
]
IGNORE_PATH_PARTS = {"__pycache__"}
IGNORE_PREFIXES = (".tmp_",)

from view.relations.module import _build_cytoscape_elements, _filter_by_focus, _should_skip_node

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
        if not _should_skip_node(node_id)
    }
    relations["edges"] = [
        edge for edge in relations.get("edges", [])
        if not _should_skip_node(edge.get("from_id", ""))
        and not _should_skip_node(edge.get("to_id", ""))
    ]

    return anchors, relations

def _html_template(elements_json: str, title: str) -> str:
    """Generate the full HTML with embedded Cytoscape.js."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script src="https://unpkg.com/cytoscape@3.28.1/dist/cytoscape.min.js"></script>
<script src="https://unpkg.com/layout-base@2.0.1/layout-base.js"></script>
<script src="https://unpkg.com/cose-base@2.2.0/cose-base.js"></script>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: #0d1117;
  color: #e6edf3;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace;
  overflow: hidden;
}}
#cy {{
  width: 100vw;
  height: 100vh;
  position: absolute;
  top: 0; left: 0;
}}
#controls {{
  position: fixed;
  top: 12px; left: 12px;
  z-index: 10;
  background: rgba(22, 27, 34, 0.95);
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 12px;
  max-width: 280px;
  backdrop-filter: blur(8px);
}}
#controls h3 {{
  font-size: 13px;
  color: #58a6ff;
  margin-bottom: 8px;
}}
#search {{
  width: 100%;
  padding: 6px 10px;
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 4px;
  color: #e6edf3;
  font-size: 12px;
  outline: none;
}}
#search:focus {{ border-color: #58a6ff; }}
.filter-group {{
  margin-top: 10px;
}}
.filter-group label {{
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #848d97;
  cursor: pointer;
  padding: 2px 0;
}}
.filter-group label:hover {{ color: #e6edf3; }}
.color-dot {{
  width: 10px; height: 10px;
  border-radius: 50%;
  display: inline-block;
}}
#legend {{
  position: fixed;
  bottom: 12px; left: 12px;
  z-index: 10;
  background: rgba(22, 27, 34, 0.95);
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 11px;
  backdrop-filter: blur(8px);
}}
#legend .item {{
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 0;
}}
#tooltip {{
  position: fixed;
  display: none;
  background: rgba(22, 27, 34, 0.97);
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 10px 14px;
  font-size: 11px;
  z-index: 20;
  max-width: 350px;
  pointer-events: none;
  line-height: 1.5;
  backdrop-filter: blur(8px);
}}
#tooltip .tt-title {{
  color: #58a6ff;
  font-weight: 600;
  font-size: 12px;
}}
#tooltip .tt-file {{ color: #848d97; }}
#tooltip .tt-io {{ color: #bc8cff; }}
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

<div id="cy"></div>

<div id="controls">
  <h3>CodeDendrite Graph</h3>
  <input type="text" id="search" placeholder="Search symbols..." autocomplete="off">
  <div class="filter-group">
    <label><input type="checkbox" data-type="call" checked><span class="color-dot" style="background:#58a6ff"></span> call</label>
    <label><input type="checkbox" data-type="inherit" checked><span class="color-dot" style="background:#3fb950"></span> inherit</label>
    <label><input type="checkbox" data-type="dataflow" checked><span class="color-dot" style="background:#bc8cff"></span> dataflow</label>
    <label><input type="checkbox" data-type="impact" checked><span class="color-dot" style="background:#f85149"></span> impact</label>
    <label><input type="checkbox" data-type="dispatch" checked><span class="color-dot" style="background:#d29922"></span> dispatch</label>
  </div>
</div>

<div id="legend">
  <div class="item"><span class="color-dot" style="background:#58a6ff"></span> call</div>
  <div class="item"><span class="color-dot" style="background:#3fb950"></span> inherit</div>
  <div class="item"><span class="color-dot" style="background:#bc8cff"></span> dataflow</div>
  <div class="item"><span class="color-dot" style="background:#f85149"></span> impact</div>
  <div class="item"><span class="color-dot" style="background:#d29922"></span> dispatch</div>
</div>

<div id="tooltip">
  <div class="tt-title"></div>
  <div class="tt-file"></div>
  <div class="tt-io"></div>
</div>

<div id="stats">
  Nodes: <span id="node-count">0</span> &nbsp;|&nbsp;
  Edges: <span id="edge-count">0</span>
</div>

<script>
const EDGE_COLORS = {{
  call: '#58a6ff',
  inherit: '#3fb950',
  dataflow: '#bc8cff',
  impact: '#f85149',
  dispatch: '#d29922'
}};

const elements = {elements_json};

const cy = cytoscape({{
  container: document.getElementById('cy'),
  elements: elements,
  style: [
    {{
      selector: '.module-container',
      style: {{
        'label': 'data(label)',
        'background-opacity': 0.05,
        'background-color': '#161b22',
        'border-color': '#30363d',
        'border-width': 1,
        'text-valign': 'top',
        'text-halign': 'center',
        'color': '#8b949e',
        'font-size': '12px',
        'padding': '18px',
      }}
    }},
    {{
      selector: 'node.symbol-node',
      style: {{
        'label': 'data(label)',
        'background-color': 'data(color)',
        'color': '#e6edf3',
        'font-size': '9px',
        'text-valign': 'bottom',
        'text-margin-y': 4,
        'width': 20,
        'height': 20,
        'border-width': 1,
        'border-color': '#30363d',
        'text-outline-width': 1,
        'text-outline-color': '#0d1117',
      }}
    }},
    {{
      selector: 'node.highlight',
      style: {{
        'border-width': 3,
        'border-color': '#f0e68c',
        'width': 30,
        'height': 30,
        'font-size': '11px',
        'z-index': 999
      }}
    }},
    {{
      selector: 'node.faded',
      style: {{ 'opacity': 0.15 }}
    }},
    {{
      selector: 'edge',
      style: {{
        'width': 1.5,
        'line-color': function(ele) {{ return EDGE_COLORS[ele.data('edge_type')] || '#444'; }},
        'target-arrow-color': function(ele) {{ return EDGE_COLORS[ele.data('edge_type')] || '#444'; }},
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
        'arrow-scale': 0.8,
        'opacity': 0.7
      }}
    }},
    {{
      selector: 'edge.faded',
      style: {{ 'opacity': 0.05 }}
    }},
    {{
      selector: 'edge.highlight',
      style: {{ 'width': 3, 'opacity': 1, 'z-index': 999 }}
    }}
  ],
  layout: {{
    name: 'cose',
    animate: false,
    fit: true,
    nodeDimensionsIncludeLabels: true,
    nodeRepulsion: function(node) {{ return 8000; }},
    idealEdgeLength: function(edge) {{ return 80; }},
    gravity: 0.3,
    numIter: 500,
    randomize: true,
    nestingFactor: 0.9,
    tile: true,
  }},
  minZoom: 0.1,
  maxZoom: 5,
  wheelSensitivity: 0.3
}});

// Stats
document.getElementById('node-count').textContent = cy.nodes().length;
document.getElementById('edge-count').textContent = cy.edges().length;

// Tooltip
const tooltip = document.getElementById('tooltip');
cy.on('mouseover', 'node', function(e) {{
  const d = e.target.data();
  tooltip.querySelector('.tt-title').textContent = d.id;
  tooltip.querySelector('.tt-file').textContent = d.file ? d.file + ':' + d.line : '';
  let ioText = '';
  if (d.inputs) ioText += 'In: ' + d.inputs + '\\n';
  if (d.outputs) ioText += 'Out: ' + d.outputs;
  tooltip.querySelector('.tt-io').textContent = ioText;
  tooltip.style.display = 'block';
}});
cy.on('mouseout', 'node', function() {{
  tooltip.style.display = 'none';
}});
cy.on('mousemove', function(e) {{
  tooltip.style.left = (e.originalEvent.clientX + 15) + 'px';
  tooltip.style.top = (e.originalEvent.clientY + 15) + 'px';
}});

// Click to highlight neighbors
cy.on('tap', 'node', function(e) {{
  const node = e.target;
  cy.elements().removeClass('highlight faded');
  const neighborhood = node.closedNeighborhood();
  neighborhood.addClass('highlight');
  cy.elements().difference(neighborhood).addClass('faded');
}});
cy.on('tap', function(e) {{
  if (e.target === cy) {{
    cy.elements().removeClass('highlight faded');
  }}
}});

// Search
document.getElementById('search').addEventListener('input', function(e) {{
  const q = e.target.value.toLowerCase().trim();
  cy.elements().removeClass('highlight faded');
  if (!q) return;
  const matched = cy.nodes().filter(function(n) {{
    if (n.data('is_parent')) return false;
    return n.data('label').toLowerCase().includes(q) || n.data('id').toLowerCase().includes(q);
  }});
  if (matched.length > 0) {{
    matched.addClass('highlight');
    cy.elements().difference(matched.closedNeighborhood()).addClass('faded');
    if (matched.length === 1) cy.animate({{ center: {{ eles: matched }}, zoom: 2, duration: 300 }});
  }}
}});

// Edge type filter
document.querySelectorAll('.filter-group input[type=checkbox]').forEach(function(cb) {{
  cb.addEventListener('change', function() {{
    const etype = this.dataset.type;
    const show = this.checked;
    cy.edges().filter(function(e) {{ return e.data('edge_type') === etype; }}).style('display', show ? 'element' : 'none');
  }});
}});
</script>
</body>
</html>'''

def generate_relation_graph(
    root: str,
    output: Optional[str] = None,
    focus: Optional[str] = None,
    radius: int = 2,
) -> str:
    """
    Generate an interactive Cytoscape.js relation graph HTML.

    Args:
        root: Project root directory
        output: Output HTML path (default: <root>/.codedendrite/relation_graph.html)
        focus: Optional node_id to center the graph on
        radius: BFS radius when focus is specified

    Returns:
        Path to the generated HTML file
    """
    anchors, relations = _load_data(root)
    edges = relations.get("edges", [])

    node_ids = None
    if focus:
        edges, node_ids = _filter_by_focus(edges, anchors, focus, radius)

    elements = _build_cytoscape_elements(edges, anchors, node_ids)

    if not output:
        output = str(Path(root) / ".codedendrite" / "relation_graph.html")

    elements_json = json.dumps(elements, ensure_ascii=False)
    title = f"CodeDendrite - {Path(root).name}"
    html = _html_template(elements_json, title)

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(html, encoding="utf-8")
    print(f"relation_graph: {output} ({len(elements)} elements)")
    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate interactive relation graph")
    parser.add_argument("root", help="Project root directory")
    parser.add_argument("--focus", default=None, help="Focus on a specific node_id")
    parser.add_argument("--radius", type=int, default=2, help="BFS radius for focus")
    parser.add_argument("--output", default=None, help="Output HTML path")
    args = parser.parse_args()

    generate_relation_graph(args.root, args.output, args.focus, args.radius)
