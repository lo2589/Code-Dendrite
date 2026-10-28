"""cdd chain → archify Architecture JSON IR。

一个文件一个节点：一条 55 行的 chain 摊成 55 个函数节点，图就读不了了；按文件聚起来，
节点数就是 chain 跨过的文件数。节点的 ``sources`` 是这个文件里落在 chain 上的函数
（最多 3 个，带行号范围），文件之间的边是索引里真实存在的调用，标签是被调函数名。
列号是文件离入口的调用深度，所以图从左到右就是调用往下走的方向。
"""
import re
from collections import OrderedDict, defaultdict
from pathlib import PurePosixPath

MAX_COLS = 12
MAX_SOURCES = 3


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


def _region_of(path):
    """文件属于哪一层：取前两级目录（src/usage、src/analyzer），顶层文件归到第一级。"""
    parts = PurePosixPath(path).parts[:-1]
    return "/".join(parts[:2]) if parts else "."


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


def _sources(anchors, symbols):
    out = []
    for aid in symbols[:MAX_SOURCES]:
        a = anchors[aid]
        start = max(1, _int(a.line_start, 1))
        end = max(start, _int(a.line_end, start))
        out.append({"path": a.file, "line": start, "end_line": end, "label": a.symbol[:48]})
    return out


def _components(anchors, files, root_file):
    rows = defaultdict(int)
    comps = []
    # 同一列里同一层的文件排相邻行，层按它最早出现的深度排：先出现的层占上面的行，
    # 各列的同层节点就落在同一排，层框才不会圈到别层的节点
    first_seen = {}
    for path, info in files.items():
        region = _region_of(path)
        first_seen[region] = min(first_seen.get(region, info["depth"]), info["depth"])
    ordered = sorted(files.items(), key=lambda kv: (
        min(kv[1]["depth"], MAX_COLS - 1), first_seen[_region_of(kv[0])], _region_of(kv[0])))
    for path, info in ordered:
        col = min(info["depth"], MAX_COLS - 1)
        name = PurePosixPath(path)
        count = len(info["symbols"])
        comps.append({
            "id": _node_id(path),
            "type": "frontend" if path == root_file else "backend",
            "label": name.name,
            # 节点宽度放不下完整目录（archify 会拒绝），只写最后一级；完整路径在 sources 里
            "sublabel": (name.parent.name or "repo root")[:24],
            "tag": "{} fn{}".format(count, "" if count == 1 else "s"),
            "sources": _sources(anchors, info["symbols"]),
            "row": rows[col],
            "col": col,
        })
        rows[col] += 1
    return comps


def _connections(links):
    out = []
    for (src, dst), names in links.items():
        label = names[0] if len(names) == 1 else "{} +{}".format(names[0], len(names) - 1)
        out.append({"from": _node_id(src), "to": _node_id(dst), "label": label[:40]})
    return out


def _box_is_clean(comps, ids):
    """archify 按被框节点的外接矩形画框：矩形里混进别层的节点，框就在说假话。"""
    inside = [c for c in comps if c["id"] in ids]
    rows = [c["row"] for c in inside]; cols = [c["col"] for c in inside]
    return not any(c["id"] not in ids and min(rows) <= c["row"] <= max(rows)
                   and min(cols) <= c["col"] <= max(cols) for c in comps)


def _gap_for(conns):
    """列间距要放得下最长的边标签（archify 按约 5.3px/字 量宽，标签两侧还要留白）。"""
    longest = max((len(c.get("label", "")) for c in conns), default=0)
    return max(56, int(longest * 5.6) + 40)


def _boundaries(files, comps):
    groups = defaultdict(list)
    for path in files:
        groups[_region_of(path)].append(_node_id(path))
    return [{"kind": "region", "label": region, "wraps": ids}
            for region, ids in groups.items()
            if region != "." and len(ids) > 1 and _box_is_clean(comps, set(ids))]


def build_architecture_ir(anchors, root_id, depth, output_name, repository=None):
    """生成 archify Architecture IR（schema_version 1，grid 布局）。"""
    if root_id not in anchors:
        raise KeyError("索引里没有这个 anchor：{}".format(root_id))
    seen, edges = collect_chain(anchors, root_id, depth)
    files, links = group_by_file(anchors, seen, edges)
    root_file = anchors[root_id].file
    comps = _components(anchors, files, root_file)
    conns = _connections(links)
    cols = max(c["col"] for c in comps) + 1
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
                   "gapX": _gap_for(conns), "gapY": 44, "cellW": 168, "cellH": 64},
        "components": comps,
        "connections": conns,
    }
    bounds = _boundaries(files, comps)
    if bounds:
        ir["boundaries"] = bounds
    stats = {"functions": len(seen), "files": len(files), "links": len(links)}
    return ir, stats
