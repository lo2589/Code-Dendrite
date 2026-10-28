"""文件节点在 archify 网格里的位置：列 = 最长调用路径，行 = 上游的平均行。

按"离入口最短的调用深度"分列时，入口直接调到的文件全挤在第 1 列：cmd_chain.py 直接
调了 6 个文件，它们叠成一竖排，所有边从一个点扇出再绕回来。这里改成分层图的老办法：

- 列：沿调用边的最长路径。一个文件既被入口直接调、又被下游某个文件调，就排到那个
  下游文件的右边，于是除了环，边都从左指向右。
- 环：DFS 里指回栈上节点的边不参与分列（它照样画，只是不推列号）。
- 行：每列按上游节点行号的平均值排（重心法），上下游尽量对齐、少交叉；平手时同一层
  （src/usage 这种）挨在一起，层框才不容易圈到别层的节点。
"""
from collections import defaultdict
from pathlib import PurePosixPath

MAX_COLS = 12


def region_of(path):
    """文件属于哪一层：取前两级目录（src/usage、src/analyzer），顶层文件归到第一级。"""
    parts = PurePosixPath(path).parts[:-1]
    return "/".join(parts[:2]) if parts else "."


def _back_edges(files, links):
    """DFS 里指回当前栈上节点的边才是环；只按 BFS 先后判会把同深度的正常调用当成回边。"""
    succ = defaultdict(list)
    for s, d in links:
        succ[s].append(d)
    state, back = {}, set()
    for start in files:
        if start in state:
            continue
        state[start] = 1
        stack = [(start, iter(succ[start]))]
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                state[node] = 2
                stack.pop()
            elif state.get(nxt) == 1:
                back.add((node, nxt))
            elif nxt not in state:
                state[nxt] = 1
                stack.append((nxt, iter(succ[nxt])))
    return back


def _columns(files, links):
    back = _back_edges(files, links)
    preds, succ, indeg = defaultdict(list), defaultdict(list), {p: 0 for p in files}
    for s, d in links:
        if (s, d) not in back:
            preds[d].append(s); succ[s].append(d); indeg[d] += 1
    col = {p: 0 for p in files}
    ready = [p for p in files if indeg[p] == 0]
    while ready:
        node = ready.pop(0)
        for d in succ[node]:
            col[d] = min(MAX_COLS - 1, max(col[d], col[node] + 1))
            indeg[d] -= 1
            if indeg[d] == 0:
                ready.append(d)
    return col, preds


def assign_grid(files, links):
    """返回 {文件路径: (col, row)}。"""
    col, preds = _columns(files, links)
    by_col = defaultdict(list)
    for path in files:
        by_col[col[path]].append(path)
    first_col = {}
    for path in files:
        region = region_of(path)
        first_col[region] = min(first_col.get(region, col[path]), col[path])
    row = {}
    for c in sorted(by_col):
        def key(path):
            ups = [row[p] for p in preds[path] if p in row]
            center = sum(ups) / len(ups) if ups else 0.0
            return (center, first_col[region_of(path)], region_of(path), path)
        for i, path in enumerate(sorted(by_col[c], key=key)):
            row[path] = i
    return {path: (col[path], row[path]) for path in files}


def box_is_clean(comps, ids):
    """archify 按被框节点的外接矩形画框：矩形里混进别层的节点，框就在说假话。"""
    inside = [c for c in comps if c["id"] in ids]
    rows = [c["row"] for c in inside]; cols = [c["col"] for c in inside]
    return not any(c["id"] not in ids and min(rows) <= c["row"] <= max(rows)
                   and min(cols) <= c["col"] <= max(cols) for c in comps)


def gap_for(conns):
    """列间距要放得下最长的边标签（archify 按约 5.3px/字 量宽，标签两侧还要留白）。"""
    longest = max((len(c.get("label", "")) for c in conns), default=0)
    return max(56, int(longest * 5.6) + 40)
