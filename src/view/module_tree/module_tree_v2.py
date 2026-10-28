"""
Module Tree V2 可视化
========================
读取 module_tree_v2.json，渲染为可搜索、可过滤的 HTML。

纯展示层，不修改模块语义、不重算 confidence/status。

用法:
    from view.module_tree.module_tree_v2 import generate_module_tree_v2_html
    path = generate_module_tree_v2_html("/path/to/project")
"""

from __future__ import annotations

import json
from pathlib import Path


# ── 状态颜色映射 ────────────────────────────────────────────────

_STATUS_COLORS = {
    "core_flow": "#2196F3",
    "independent_capability": "#4CAF50",
    "support_utility": "#FF9800",
    "dormant": "#9E9E9E",
    "uncertain": "#F44336",
}

_CONFIDENCE_BADGES = {
    "A": ("A", "#4CAF50"),
    "B": ("B", "#8BC34A"),
    "C": ("C", "#FF9800"),
    "D": ("D", "#F44336"),
}


# ── HTML 模板 ───────────────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Module Tree V2 - {project_name}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #f5f5f5; color: #333; padding: 20px; }}

.header {{ background: #1a1a2e; color: #fff; padding: 24px 32px; border-radius: 12px;
           margin-bottom: 24px; }}
.header h1 {{ font-size: 24px; margin-bottom: 8px; }}
.header .stats {{ display: flex; gap: 24px; flex-wrap: wrap; }}
.header .stat {{ background: rgba(255,255,255,0.1); padding: 8px 16px; border-radius: 8px;
                 font-size: 14px; }}
.header .stat strong {{ color: #64ffda; }}

.controls {{ display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; align-items: center; }}
.controls input {{ padding: 8px 16px; border: 1px solid #ddd; border-radius: 8px;
                   font-size: 14px; min-width: 240px; }}
.controls .filter-btn {{ padding: 6px 14px; border: 2px solid #ddd; border-radius: 20px;
                         background: #fff; cursor: pointer; font-size: 13px; transition: 0.2s; }}
.controls .filter-btn:hover {{ border-color: #999; }}
.controls .filter-btn.active {{ border-color: #2196F3; background: #E3F2FD; color: #1565C0; }}

.modules {{ display: grid; gap: 16px; }}

.module-card {{ background: #fff; border-radius: 12px; padding: 20px; border-left: 5px solid #ccc;
                box-shadow: 0 2px 8px rgba(0,0,0,0.06); transition: 0.2s; }}
.module-card:hover {{ box-shadow: 0 4px 16px rgba(0,0,0,0.12); transform: translateY(-1px); }}

.module-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }}
.module-name {{ font-size: 18px; font-weight: 600; flex: 1; }}
.badge {{ display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px;
          font-weight: 700; color: #fff; }}
.status-tag {{ font-size: 12px; padding: 3px 10px; border-radius: 4px; background: #eee; color: #555; }}

.module-body {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
.slot {{ padding: 10px 14px; background: #fafafa; border-radius: 8px; }}
.slot-label {{ font-size: 11px; font-weight: 700; color: #888; text-transform: uppercase;
               margin-bottom: 4px; }}
.slot-value {{ font-size: 13px; line-height: 1.5; }}
/* How 是一步一行的实现过程：占满整行、保留换行，长路径不折断成乱码 */
.slot.how, .slot.wide {{ grid-column: 1 / -1; }}
.slot.how .slot-value {{ white-space: pre; overflow-x: auto; font-family: ui-monospace, Menlo, monospace; font-size: 12px; }}

.evidence-section {{ margin-top: 12px; padding-top: 12px; border-top: 1px solid #eee; }}
.evidence-chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }}
.chip {{ font-size: 11px; padding: 2px 8px; background: #E8EAF6; border-radius: 10px; color: #3F51B5; }}
.chip.test {{ background: #FFF3E0; color: #E65100; }}
.chip.file {{ background: #E8F5E9; color: #2E7D32; }}

.completeness {{ background: #fff; border-radius: 12px; padding: 20px; margin-top: 24px;
                 box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
.completeness h2 {{ font-size: 18px; margin-bottom: 16px; }}
.warning {{ padding: 8px 14px; background: #FFF8E1; border-left: 3px solid #FFC107;
            margin-bottom: 8px; border-radius: 4px; font-size: 13px; }}
.error {{ padding: 8px 14px; background: #FFEBEE; border-left: 3px solid #F44336;
          margin-bottom: 8px; border-radius: 4px; font-size: 13px; }}
.ok {{ padding: 8px 14px; background: #E8F5E9; border-left: 3px solid #4CAF50;
       margin-bottom: 8px; border-radius: 4px; font-size: 13px; }}

.hidden {{ display: none !important; }}
</style>
</head>
<body>

<div class="header">
  <h1>Module Tree V2</h1>
  <div class="stats">
    <div class="stat">模块数 <strong>{total_modules}</strong></div>
    <div class="stat">模块间边 <strong>{total_edges}</strong></div>
    {status_stats}
    {confidence_stats}
  </div>
</div>

<div class="controls">
  <input type="text" id="search" placeholder="搜索模块名 / 文件名 / 符号名..." oninput="filterModules()">
  <button class="filter-btn active" onclick="toggleFilter(this, 'all')">全部</button>
  <button class="filter-btn" onclick="toggleFilter(this, 'core_flow')">core_flow</button>
  <button class="filter-btn" onclick="toggleFilter(this, 'independent_capability')">independent</button>
  <button class="filter-btn" onclick="toggleFilter(this, 'support_utility')">support</button>
  <button class="filter-btn" onclick="toggleFilter(this, 'dormant')">dormant</button>
  <button class="filter-btn" onclick="toggleFilter(this, 'uncertain')">uncertain</button>
</div>

<div class="modules" id="modules">
{module_cards}
</div>

<div class="completeness">
  <h2>完整性报告</h2>
  {completeness_html}
</div>

<script>
let activeFilter = 'all';

function toggleFilter(btn, filter) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  activeFilter = filter;
  filterModules();
}}

function filterModules() {{
  const query = document.getElementById('search').value.toLowerCase();
  document.querySelectorAll('.module-card').forEach(card => {{
    const text = card.textContent.toLowerCase();
    const status = card.dataset.status;
    const matchQuery = !query || text.includes(query);
    const matchFilter = activeFilter === 'all' || status === activeFilter;
    card.classList.toggle('hidden', !(matchQuery && matchFilter));
  }});
}}
</script>
</body>
</html>"""


# ── 渲染函数 ────────────────────────────────────────────────────

def _render_module_card(module: dict) -> str:
    """渲染单个模块卡片。"""
    status = module.get("status", "uncertain")
    confidence = module.get("confidence", "D")
    name = module.get("name", "unknown")
    color = _STATUS_COLORS.get(status, "#ccc")
    badge_label, badge_color = _CONFIDENCE_BADGES.get(confidence, ("?", "#999"))

    # 四格
    what = module.get("what", "") or "unknown"
    how = module.get("how", "") or "to_verify"
    functions = module.get("functions", [])
    role = module.get("role", "") or "to_verify"

    funcs_html = ""
    for f in functions[:6]:
        short = f.split("::")[-1] if "::" in f else f
        funcs_html += f'<code>{_esc(short)}</code> '

    # 证据
    evidence = module.get("evidence", {})
    evidence_html = ""

    files = module.get("files", [])
    if files:
        chips = "".join(f'<span class="chip file">{_esc(f)}</span>' for f in files[:8])
        if len(files) > 8:
            chips += f'<span class="chip file">+{len(files)-8} more</span>'
        evidence_html += f'<div><span class="slot-label">文件 ({len(files)})</span><div class="evidence-chips">{chips}</div></div>'

    tests = evidence.get("tests", [])
    if tests:
        chips = "".join(f'<span class="chip test">{_esc(t.split("::")[-1] if "::" in t else t)}</span>' for t in tests[:5])
        evidence_html += f'<div style="margin-top:6px"><span class="slot-label">测试证据</span><div class="evidence-chips">{chips}</div></div>'

    return f"""
<div class="module-card" data-status="{status}" style="border-left-color:{color}">
  <div class="module-header">
    <span class="module-name">{_esc(name)}</span>
    <span class="badge" style="background:{badge_color}">{badge_label}</span>
    <span class="status-tag" style="color:{color}">{status}</span>
  </div>
  <div class="module-body">
    <div class="slot"><div class="slot-label">What</div><div class="slot-value">{_esc(what)}</div></div>
    <div class="slot"><div class="slot-label">Role</div><div class="slot-value">{_esc(role)}</div></div>
    <div class="slot how"><div class="slot-label">How</div><div class="slot-value">{_esc(how)}</div></div>
    <div class="slot wide"><div class="slot-label">Functions</div><div class="slot-value">{funcs_html or '-'}</div></div>
  </div>
  <div class="evidence-section">{evidence_html}</div>
</div>"""


def _render_completeness(comp: dict) -> str:
    """渲染完整性报告。"""
    html = ""

    # 区域覆盖
    ac = comp.get("area_coverage", {})
    total = ac.get("total_areas", 0)
    covered = ac.get("covered", 0)
    uncovered = ac.get("uncovered", [])

    if total == covered and total > 0:
        html += f'<div class="ok">区域覆盖: {covered}/{total} (100%)</div>'
    elif total > 0:
        html += f'<div class="warning">区域覆盖: {covered}/{total}，未覆盖: {", ".join(uncovered)}</div>'

    # 假模块警告
    for w in comp.get("fake_module_warnings", []):
        html += f'<div class="error">可能的假模块: {_esc(w.get("name", ""))} - {_esc(w.get("reason", ""))}</div>'

    # 低信心
    for lc in comp.get("low_confidence_modules", []):
        html += f'<div class="warning">低信心: {_esc(lc.get("name", ""))} (confidence={lc.get("confidence", "")})</div>'

    # 证据不足
    for me in comp.get("missing_evidence", []):
        missing = ", ".join(me.get("missing", []))
        html += f'<div class="warning">证据不足: {_esc(me.get("name", ""))} - 缺少 {missing}</div>'

    if not html:
        html = '<div class="ok">所有检查通过，无警告。</div>'

    return html


def _esc(text: str) -> str:
    """HTML 转义。"""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ── 主入口 ──────────────────────────────────────────────────────

def generate_module_tree_v2_html(root: str = ".", output: str = None) -> str:
    """渲染 Module Tree V2 HTML。

    Args:
        root: 项目根目录（含 .codedendrite/module_tree_v2.json）
        output: 可选输出路径

    Returns:
        HTML 文件绝对路径
    """
    tree_path = Path(root) / ".codedendrite" / "module_tree_v2.json"
    if not tree_path.exists():
        raise FileNotFoundError(f"module_tree_v2.json not found: {tree_path}")

    with open(tree_path, "r", encoding="utf-8") as f:
        tree = json.load(f)

    modules = tree.get("modules", [])
    edges = tree.get("edges", [])
    summary = tree.get("summary", {})
    completeness = tree.get("completeness", {})

    # 渲染模块卡片
    cards_html = "\n".join(_render_module_card(m) for m in modules)

    # 渲染状态统计
    by_status = summary.get("by_status", {})
    status_stats = ""
    for st, count in by_status.items():
        color = _STATUS_COLORS.get(st, "#999")
        status_stats += f'<div class="stat" style="border-left:3px solid {color}">{st} <strong>{count}</strong></div>'

    # 渲染信心统计
    by_confidence = summary.get("by_confidence", {})
    conf_stats = ""
    for cf, count in sorted(by_confidence.items()):
        _, color = _CONFIDENCE_BADGES.get(cf, ("?", "#999"))
        conf_stats += f'<div class="stat" style="border-left:3px solid {color}">Confidence {cf} <strong>{count}</strong></div>'

    # 渲染完整性
    comp_html = _render_completeness(completeness)

    # 组装 HTML
    project_name = Path(root).resolve().name
    html = _HTML_TEMPLATE.format(
        project_name=_esc(project_name),
        total_modules=len(modules),
        total_edges=len(edges),
        status_stats=status_stats,
        confidence_stats=conf_stats,
        module_cards=cards_html,
        completeness_html=comp_html,
    )

    # 写文件
    if output:
        out_path = Path(output)
    else:
        out_path = Path(root) / ".codedendrite" / "module_tree_v2.html"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    return str(out_path.resolve())


# ── 主入口（直接运行）──────────────────────────────────────────

if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    path = generate_module_tree_v2_html(root)
    print(f"HTML 已生成: {path}")
