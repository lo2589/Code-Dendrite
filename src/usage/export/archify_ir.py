"""cdd chain → archify Architecture JSON IR。

一个文件一个节点：一条 55 行的 chain 摊成 55 个函数节点，图就读不了了；按文件聚起来，
节点数就是 chain 跨过的文件数。节点的 ``sources`` 是这个文件里落在 chain 上的函数
（最多 3 个，带行号范围），文件之间的边是索引里真实存在的调用，标签是被调函数名。
位置由 archify_layout 算：列是最长调用路径（边都从左指向右），行按上游对齐。
"""
import re
from collections import Counter, OrderedDict, defaultdict
from pathlib import PurePosixPath

from usage.export.archify_layout import assign_grid, box_is_clean, gap_for, region_of

MAX_SOURCES = 3
NODE_H = 60
LABEL_CAPS = (20, 16, 12, 8)
# archify 在 1440px 桌面上要求整张图宽 ≤ 1794px；留点余量
WIDTH_BUDGET = 1760


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def collect_chain(anchors, root_id, depth):
    """从 root_id 顺着 callees 广度优先走 depth 层。返回 ({anchor_id: 深度}, [(caller, callee)])。"""
    seen = OrderedDict({root_id: 0})
    edges = []
    frontier = [root_id]
    for level in range(1, depth + 1):
        nxt = []
        for aid in frontier:
            for callee in getattr(anchors[aid], "callees", None) or []:
                if callee not in anchors or callee == aid:
                    continue
                edges.append((aid, callee))
                if callee not in seen:
                    seen[callee] = level
                    nxt.append(callee)
        frontier = nxt
    return seen, edges


def _node_id(path):
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", path).strip("_")
    return "f_" + slug


def group_by_file(anchors, seen, edges):
    """聚成文件节点和文件间的边。文件深度取它里面最浅的那个函数。"""
    files = OrderedDict()
    for aid, level in seen.items():
        a = anchors[aid]
        entry = files.setdefault(a.file, {"depth": level, "symbols": []})
        entry["depth"] = min(entry["depth"], level)
        entry["symbols"].append(aid)
    links = OrderedDict()
    for caller, callee in edges:
        src, dst = anchors[caller].file, anchors[callee].file
        if src == dst:
            continue
        names = links.setdefault((src, dst), [])
        name = anchors[callee].symbol
        if name not in names:
            names.append(name)
    return files, links


def _node_width(label):
    """节点要放得下文件名：archify 量标签约 6.6px/字，默认 120px 放不下 get_downward_chain.py。"""
    return max(120, int(len(label) * 7) + 28)


def _sources(anchors, symbols):
    out = []
    for aid in symbols[:MAX_SOURCES]:
        a = anchors[aid]
        start = max(1, _int(a.line_start, 1))
        end = max(start, _int(a.line_end, start))
        out.append({"path": a.file, "line": start, "end_line": end, "label": a.symbol[:48]})
    return out


def _sublabel(path, names):
    """副标题是目录。同名文件（两个 core.py）只写最后一级就分不清，改写最后两级。"""
    parent = PurePosixPath(path).parent
    if names[PurePosixPath(path).name] > 1 and len(parent.parts) > 1:
        return "/".join(parent.parts[-2:])[-24:]
    return (parent.name or "repo root")[:24]


def _components(anchors, files, links, root_file):
    grid = assign_grid(files, links)
    names = Counter(PurePosixPath(p).name for p in files)
    comps = []
    for path, info in sorted(files.items(), key=lambda kv: grid[kv[0]]):
        col, row = grid[path]
        name = PurePosixPath(path)
        count = len(info["symbols"])
        comps.append({
            "id": _node_id(path),
            "type": "frontend" if path == root_file else "backend",
            "label": name.name,
            # 节点宽度放不下完整目录（archify 会拒绝）；完整路径在 sources 里
            "sublabel": _sublabel(path, names),
            "tag": "{} fn{}".format(count, "" if count == 1 else "s"),
            "sources": _sources(anchors, info["symbols"]),
            "size": [_node_width(name.name), NODE_H],
            "row": row,
            "col": col,
        })
    return comps


def _connections(links, cap):
    out = []
    for (src, dst), names in links.items():
        # 标签决定列间距，太长整张图会超出 archify 的桌面宽度上限；全名在节点的 SRC 里
        name = names[0] if len(names[0]) <= cap else names[0][:cap - 1] + "…"
        label = name if len(names) == 1 else "{} +{}".format(name, len(names) - 1)
        out.append({"from": _node_id(src), "to": _node_id(dst), "label": label})
    return out


def _fit_connections(links, cols, cell_w):
    """边标签逐级截短，直到整张图（原点 + 各列 + 列间距）放得进 archify 的宽度上限。"""
    for cap in LABEL_CAPS:
        conns = _connections(links, cap)
        if 40 + cols * cell_w + (cols - 1) * gap_for(conns) <= WIDTH_BUDGET:
            return conns
    return conns


def _boundaries(files, comps):
    groups = defaultdict(list)
    for path in files:
        groups[region_of(path)].append(_node_id(path))
    return [{"kind": "region", "label": region, "wraps": ids}
            for region, ids in groups.items()
            # 框住全部节点的框不提供任何信息
            if region != "." and 1 < len(ids) < len(files) and box_is_clean(comps, set(ids))]


def build_architecture_ir(anchors, root_id, depth, output_name, repository=None):
    """生成 archify Architecture IR（schema_version 1，grid 布局）。"""
    if root_id not in anchors:
        raise KeyError("索引里没有这个 anchor：{}".format(root_id))
    seen, edges = collect_chain(anchors, root_id, depth)
    files, links = group_by_file(anchors, seen, edges)
    root_file = anchors[root_id].file
    comps = _components(anchors, files, links, root_file)
    cols = max(c["col"] for c in comps) + 1
    cell_w = max(168, max(c["size"][0] for c in comps) + 16)
    conns = _fit_connections(links, cols, cell_w)
    meta = {
        "title": anchors[root_id].symbol,
        "subtitle": "cdd chain {} · {} functions in {} files · edges from static analysis".format(
            root_id, len(seen), len(files)),
        "output": output_name,
        "quality_profile": "showcase",
        "legend": {"mode": "auto", "entries": {
            "frontend": {"label": "entry file"},
            "backend": {"label": "file reached by calls"},
        }},
    }
    if repository:
        meta["repository"] = repository
    ir = {
        "schema_version": 1,
        "diagram_type": "architecture",
        "meta": meta,
        "layout": {"mode": "grid", "origin": [40, 110], "cols": cols,
                   "gapX": gap_for(conns), "gapY": 44, "cellW": cell_w, "cellH": 64},
        "components": comps,
        "connections": conns,
    }
    bounds = _boundaries(files, comps)
    if bounds:
        ir["boundaries"] = bounds
    stats = {"functions": len(seen), "files": len(files), "links": len(links)}
    return ir, stats
