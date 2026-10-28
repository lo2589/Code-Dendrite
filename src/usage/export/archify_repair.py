"""archify 校验通过 ≠ 读得懂：再查一遍线和标签，查出歧义就改 IR 重排。

archify 的检查管的是版面合法（不穿节点、不出画布），管不到"读的人会不会认错"。实测
build_jump_packet 那张图全部通过，却有两条边在顶部同一条通道里并了 351px，看上去是一条
线；一个 load_anchors 标签离自己的线 40px，夹在两条线中间认不出是谁的。

这里读 ``archify validate --layout-json`` 给出的实际走线和标签框，查三件事：

- 标签离自己的线太远，或者离别的线比离自己的近 → 用 ``labelSegment`` 把它钉到自己
  更长的一段上（按段长从长到短轮着试）
- 两条不同的边共用一段通道 → 先换其中一条的出入侧（fromSide / toSide），让 archify 自己
  另找通道；不行再用 ``via`` 把那段挪开 14 / 28px（手写的 via 一和别的线交叉就不合法，
  所以排在后面）
- 线的端点没落在两头节点的边框上

改法一次只试一个，交给 archify 校验：它接受、并且问题确实变少，才留下。一次改两处的
做法试过——一处改坏就整轮作废，剩下的备选再也轮不到。
"""
import json
import math

LABEL_GAP = 14       # 标签框离自己的线超过这个距离，就认不出是谁的（archify 默认放在约 10px 处）
LABEL_MARGIN = 6     # 离别的线不比离自己的远出这么多，两条线就分不清
CROWD_GAP = 8        # 别的线离标签框不到这个距离，就算压在自己线上也分不清
SHARED_MIN = 8       # 两条边共线超过这个长度，就看成一条线
SHIFT = 14


def _seg_rect_gap(a, b, r):
    """轴向线段到矩形的最短距离（相交为 0）。"""
    (x1, y1), (x2, y2) = a, b
    lx, rx, ty, by = r["x"], r["x"] + r["width"], r["y"], r["y"] + r["height"]
    dx = max(lx - max(x1, x2), 0, min(x1, x2) - rx)
    dy = max(ty - max(y1, y2), 0, min(y1, y2) - by)
    return math.hypot(dx, dy)


def _route_rect_gap(points, rect):
    return min(_seg_rect_gap(points[i], points[i + 1], rect) for i in range(len(points) - 1))


def _shared(a, b):
    (ax1, ay1), (ax2, ay2) = a
    (bx1, by1), (bx2, by2) = b
    if ay1 == ay2 and by1 == by2 and abs(ay1 - by1) <= 3:
        return max(0, min(max(ax1, ax2), max(bx1, bx2)) - max(min(ax1, ax2), min(bx1, bx2)))
    if ax1 == ax2 and bx1 == bx2 and abs(ax1 - bx1) <= 3:
        return max(0, min(max(ay1, ay2), max(by1, by2)) - max(min(ay1, ay2), min(by1, by2)))
    return 0


def _on_border(pt, r, tol=2.5):
    x, y = pt
    in_x = r["x"] - tol <= x <= r["x"] + r["width"] + tol
    in_y = r["y"] - tol <= y <= r["y"] + r["height"] + tol
    return (in_y and min(abs(x - r["x"]), abs(x - r["x"] - r["width"])) <= tol) or \
           (in_x and min(abs(y - r["y"]), abs(y - r["y"] - r["height"])) <= tol)


def audit(layout):
    """返回 [(种类, 连接下标, 细节)]：label / shared / endpoint。"""
    comps = {c["id"]: c for c in layout["components"]}
    conns = layout["connections"]
    problems = []
    for i, c in enumerate(conns):
        pts = c["points"]
        if not (_on_border(pts[0], comps[c["from"]]) and _on_border(pts[-1], comps[c["to"]])):
            problems.append(("endpoint", i, {}))
    # 标签和连接按 labelAt 对上：同名标签（三个 get_anchor）不能按文字对
    for i, c in enumerate(conns):
        lab = next((l for l in layout.get("labels", []) if l.get("labelAt") == c.get("labelAt")
                    and l.get("text") == c.get("label")), None)
        if lab is None:
            continue
        own = _route_rect_gap(c["points"], lab)
        other = min((_route_rect_gap(o["points"], lab) for j, o in enumerate(conns) if j != i), default=math.inf)
        if own > LABEL_GAP or other < own + LABEL_MARGIN or other < CROWD_GAP:
            problems.append(("label", i, {"own": round(own, 1), "other": round(other, 1)}))
    for i, c in enumerate(conns):
        for j in range(i + 1, len(conns)):
            o = conns[j]
            for k in range(len(o["points"]) - 1):
                length = sum(_shared(c["points"][m:m + 2], o["points"][k:k + 2]) for m in range(len(c["points"]) - 1))
                if length > SHARED_MIN:
                    problems.append(("shared", j, {"with": i, "segment": k, "length": round(length)}))
    return problems


def _segments_by_length(points):
    lengths = [abs(points[i + 1][0] - points[i][0]) + abs(points[i + 1][1] - points[i][1]) for i in range(len(points) - 1)]
    return sorted(range(len(lengths)), key=lambda i: -lengths[i])


def _shifted_via(points, k, delta):
    """把第 k 段（两头都在路线中间）平移 delta，返回新的 via（去掉首尾端点）。"""
    if k < 1 or k + 1 > len(points) - 2:
        return None
    pts = [list(p) for p in points]
    axis = 1 if pts[k][1] == pts[k + 1][1] else 0
    pts[k][axis] += delta
    pts[k + 1][axis] += delta
    return [[round(x, 1), round(y, 1)] for x, y in pts[1:-1]]


# 只换上下：布局里边都从左指向右，让它从左边出、或者从右边进，线就得往回绕一圈
_SIDE_MOVES = (("fromSide", "bottom"), ("toSide", "bottom"), ("fromSide", "top"), ("toSide", "top"))


def _candidates(problem, layout):
    """一个问题的备选改法，每个是 {连接下标: {字段: 值}}，按改动从小到大排。"""
    kind, i, info = problem
    conns = layout["connections"]
    if kind == "label":
        moves = [{i: {"labelSegment": seg}} for seg in _segments_by_length(conns[i]["points"])]
        return moves + [{i: {side: value}} for side, value in _SIDE_MOVES]
    if kind == "shared":
        # 先换出入侧：走线仍由 archify 自动排，允许带白边的交叉；手写 via 的线一交叉就不合法
        out = [{target: {side: value}} for target in (i, info["with"]) for side, value in _SIDE_MOVES]
        for target in (i, info["with"]):
            pts = conns[target]["points"]
            for k in range(len(pts) - 1):
                if sum(_shared(pts[k:k + 2], conns[o]["points"][m:m + 2])
                       for o in (i, info["with"]) if o != target
                       for m in range(len(conns[o]["points"]) - 1)) <= SHARED_MIN:
                    continue
                for delta in (SHIFT, -SHIFT, 2 * SHIFT, -2 * SHIFT):
                    via = _shifted_via(pts, k, delta)
                    if via:
                        out.append({target: {"via": via, "route": None}})
        return out
    return []


def _apply(ir, change):
    trial = json.loads(json.dumps(ir))
    for idx, fields in change.items():
        for key, value in fields.items():
            if value is None:
                trial["connections"][idx].pop(key, None)
            else:
                trial["connections"][idx][key] = value
    return trial


def polish(ir, validate, max_tries=40):
    """一次只试一个改动，archify 接受且问题变少才留下。validate(ir) 返回 layout 或 None。
    返回 (改好的 ir, 还剩的问题描述)。"""
    layout = validate(ir)
    if layout is None:
        return ir, []
    problems, tries = audit(layout), 0
    while problems and tries < max_tries:
        accepted = False
        for problem in problems:
            for change in _candidates(problem, layout):
                tries += 1
                trial = _apply(ir, change)
                trial_layout = validate(trial)
                if trial_layout is not None:
                    trial_problems = audit(trial_layout)
                    if len(trial_problems) < len(problems):
                        ir, layout, problems, accepted = trial, trial_layout, trial_problems, True
                        break
                if tries >= max_tries:
                    break
            if accepted or tries >= max_tries:
                break
        if not accepted:
            break
    return ir, [describe(p, layout) for p in problems]


def describe(problem, layout):
    kind, i, info = problem
    c = layout["connections"][i]
    name = "{} → {}（{}）".format(c["from"], c["to"], c.get("label", ""))
    if kind == "label":
        return "标签离自己的线 {}px，离别的线 {}px：{}".format(info["own"], info["other"], name)
    if kind == "shared":
        return "和另一条边并线 {}px：{}".format(info["length"], name)
    return "端点没落在节点边框上：" + name
