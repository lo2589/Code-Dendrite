"""
Relations API.

Generate and query the persisted relation graph in `.codedendrite/relations.json`.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

from analyzer.shared.types import Edge

from api.relations.load_relations import _build_id_index, _build_virtual_skip_pairs, _callee_condition, _callee_seq, _callee_target, _edge_hash, _iter_call_refs, _norm, _resolve_id


def _module_of(anchor_id: str) -> str:
    """一个 anchor 属于哪个模块——impact 边靠它判断"几个模块依赖了这个目标"。

    代码住在 <root>/src/<层>/... 下，所以只取第一段会把所有文件都算成同一个
    模块 "src"，impact 边会因此全部消失。src/ 开头时取两层。
    """
    path = anchor_id.replace("\\", "/").split("::")[0]
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "src":
        return f"src/{parts[1]}"
    return parts[0] if parts else path


# 一条边每一轮都会重算（state 边），旧的一律丢
_ALWAYS = "\u0000always"


def _file_of(anchor_id: str) -> str:
    """一条边端点的文件部分。id 是 `file::symbol`，符号里不会再出现 `::`。"""
    return str(anchor_id).replace("\\", "/").split("::", 1)[0]


def _edge_kinds(item: dict) -> set:
    """一条 dataflow 边的 kind 集合（arg / return / relay / state）。"""
    evidence = str(item.get("evidence", ""))
    if not evidence.startswith("strict-dataflow:"):
        return set()
    return {k for k in evidence.split(":", 1)[1].split("+") if k}


def _class_key(anchor_id: str) -> str:
    """`file::Class.method` -> `file::Class`。state 边按类重算，靠它认类。"""
    text = str(anchor_id)
    return text.rsplit(".", 1)[0] if "." in text.split("::")[-1] else text


def _edge_emitter(item: dict, relay_emitters: dict) -> str:
    """这条旧的 dataflow 边是**在谁的分析里**发出来的。

    这是增量最关键的一处：一条边由谁产生，和这条边的两端是谁，不是一回事。

      arg     f -> g   分析 f 时发出，emitter = from
      return  g -> f   分析 f 时发出，emitter = to（from 是那个没改的 callee）
      relay   p -> g   分析 f 时发出，p 和 g 都不是 emitter
      state   w -> r   同上

    按 from_id 丢旧边，会顺手丢掉 `return` 那一批——它们的主人没改，改的是
    调用它的那个文件，于是"改一个文件"会把一堆无辜的返回边连坐掉。
    `relay` 的两端都不是 emitter，只能查表——表跟着 relations.json 的 meta 一起写。
    表里没有（老索引、或第一次增量）就返回空串，调用方按"保守不丢"处理：
    宁可让一条该消失的 relay 边多活一轮，也不能把没重算过的边当脏边丢掉。
    """
    kinds = _edge_kinds(item)
    if "return" in kinds:
        return str(item.get("to_id", ""))
    if "arg" in kinds:
        return str(item.get("from_id", ""))
    if kinds == {"state"}:
        # state 段按**类**重算：这个类脏了才丢旧边，没脏的类原样保留。
        return "\u0000state:" + _class_key(item.get("from_id", ""))
    if "relay" in kinds:
        key = _edge_key_text(item)
        return str(relay_emitters.get(key, ""))
    return str(item.get("from_id", ""))


def _edge_key_text(item: dict) -> str:
    """一条边的去重键。

    必须和 `_add_edge` 的键同口径：少了 `edge_type`，同一对 anchor 之间的
    call 边和 dataflow 边会撞成一条，合并时后到的那条被当成重复丢掉——9 条
    call 边就是这么没的。dispatch 的键还带 dispatch_key/value 和 scope_label，
    这里一并带上。
    """
    return "\u0000".join([
        str(item.get("from_id", "")),
        str(item.get("to_id", "")),
        str(item.get("edge_type", "")),
        str(item.get("condition") or ""),
        str(item.get("dispatch_key") or ""),
        str(item.get("dispatch_value") or ""),
        str(item.get("scope_label") or ""),
    ])


def _previous(output_path: Path) -> tuple:
    """上一次写下的边 + relay 边到 emitter 的表。读不出来就是没有。"""
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], {}
    edges = payload.get("edges")
    emitters = payload.get("meta", {}).get("relay_emitters")
    return (edges if isinstance(edges, list) else [],
            emitters if isinstance(emitters, dict) else {})


def _dirty_sources(anchors, id_index, previous: list, changed_files, relay_emitters) -> set:
    """哪些 anchor 的**出边**可能变了——增量必须精确覆盖它，多一点没关系。

    一条边只可能因为下面五种原因变化，所以脏集是这五条的并集：

    1. 边的主人就在改动文件里（它自己的调用点/输入输出变了）；
    2. 上一条索引里，这条边指向改动文件（`to_id` 在改动文件里）——包括
       被删掉的符号：文件没了，指向它的旧边必须跟着消失，而边的这一端
       一个字都没改；
    3. 上一条索引里，这条边的主人就在改动文件里（文件被删时 `from_id`
       已经不在新 anchor 表里，只能从旧边里认出来）；
    4. 边的主人按名字引用了改动文件里的符号——改名会让分辨率变化，而引用方
       可能没被改（`old_name` 消失后连解析都失败了，靠 2 也找不到新名字）；
    5. 改动文件里的 anchor 所调用的 callee。这条最容易被漏掉：dataflow 的
       `return`/`relay` 边是 **callee -> caller**，边的 from 端住在没改的那个
       文件里。新增一个文件去调用老函数，老函数就凭空多一条出边；只按
       "文件在改动集里"收脏集，这条边永远补不回来。

    少收了就是索引漂，多收了只是白算几条，所以第 4 条按"名字出现过"而不是
    "名字解析得上"来收。
    """
    changed = {_norm(f) for f in (changed_files or [])}
    if not changed:
        return set()

    dirty: set = set()
    for anchor in anchors.values():
        if _norm(anchor.file) not in changed:
            continue
        dirty.add(_norm(anchor.id))
        for raw_callee in _iter_call_refs(anchor):
            target = _callee_target(raw_callee)
            if not target:
                continue
            callee = _resolve_id(target, id_index)
            if callee is not None:
                dirty.add(_norm(callee.id))

    # 2/3. 上一条索引里碰到改动文件的边：要重算的是**发出它的人**，不是它的
    #      from 端。relay 边（p -> g 由 f 发出）和 return 边（g -> f 由 f 发出）
    #     在这里会走岔——按 from 端收脏集，那个真正需要重算的 f 永远进不来，
    #     被删掉的 relay 边就会作为幽灵留在图上。
    for edge in previous:
        from_id = str(edge.get("from_id", ""))
        to_id = str(edge.get("to_id", ""))
        touches = (_norm(_file_of(to_id)) in changed or _norm(_file_of(from_id)) in changed)
        if not touches:
            continue
        emitter = _edge_emitter(edge, relay_emitters)
        if emitter and emitter != _ALWAYS:
            dirty.add(_norm(emitter))
        if from_id:
            dirty.add(_norm(from_id))

    # 4. 引用方按名字解析到改动文件里的 anchor——现在才解析得上（新符号）的那批。
    #    判据是"解析结果落在改动文件里"，不是"名字在改动文件里出现过"。后者会把
    #    全库同名的符号（`__init__` 一个名字就命中 1449 个 anchor）整片拖进脏集：
    #    实测 3538 个脏 anchor 里有 3005 个是这么来的，增量直接退化回全量。
    for anchor in anchors.values():
        for raw_callee in _iter_call_refs(anchor):
            target = _callee_target(raw_callee)
            if not target:
                continue
            resolved = _resolve_id(target, id_index)
            if resolved is not None and _norm(resolved.file) in changed:
                dirty.add(_norm(anchor.id))
                break

    return dirty


def generate_relations(root: str = ".", changed_files: Optional[List[str]] = None) -> dict:
    """重建因果边。

    `changed_files` 给了就是增量：只重算脏集里那些 anchor 的出边，其余边原样
    从上一份 relations.json 搬过来。不给就是全量，行为和以前一样。

    判据只有一条，写在 test_incremental_relations_v1_26.py 里：同一个变更集，
    两条路走出来的边必须逐条相等。少一条就是索引漂了。
    """
    root_path = Path(root)
    output_path = root_path / ".codedendrite" / "relations.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # edge_map: (from_id, to_id, edge_type, condition, scope_label) -> Edge
    # 同一对节点的多次调用合并 seq 列表
    edge_map: dict[tuple, Edge] = {}
    failed: list[str] = []

    dirty: Optional[set] = None
    dirty_classes: set = set()
    previous: list = []
    relay_emitters: dict = {}
    if changed_files is not None:
        previous, relay_emitters = _previous(output_path)

    def _affected(anchor_id: str) -> bool:
        """增量模式下这个 from 是否要重算。全量模式恒真。"""
        return dirty is None or _norm(anchor_id) in dirty

    def _add_edge(edge: Edge) -> None:
        if edge.edge_type == "dispatch" or edge.condition or edge.scope_label:
            key = (
                edge.from_id,
                edge.to_id,
                edge.edge_type,
                edge.condition,
                edge.dispatch_key,
                edge.dispatch_value,
                edge.scope_label,
            )
        else:
            key = (edge.from_id, edge.to_id, edge.edge_type, None, None, None, None)

        if key in edge_map:
            edge_map[key].seq.extend(s for s in edge.seq if s not in edge_map[key].seq)
        else:
            edge_map[key] = edge

    try:
        from analyzer.anchors import load_anchors

        anchors = load_anchors(str(root_path))
        id_index = _build_id_index(anchors)
        skip_pairs = _build_virtual_skip_pairs(anchors)
        if changed_files is not None:
            dirty = _dirty_sources(anchors, id_index, previous, changed_files,
                                   relay_emitters)
            # state 边按类重算，这里算出脏类，合并时按类决定旧边丢不丢
            dirty_classes = {_norm(_class_key(a.id)) for a in anchors.values()
                             if _norm(a.id) in dirty}

        # Precompute (caller_id, callee_id) -> call-site refs for edge metadata.
        callee_ref_map: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for anchor in anchors.values():
            norm_anchor_id = _norm(anchor.id)
            for raw_callee in _iter_call_refs(anchor):
                target = _callee_target(raw_callee)
                if target:
                    site = dict(raw_callee) if isinstance(raw_callee, dict) else {"target": target}
                    site.setdefault("seq", _callee_seq(raw_callee))
                    callee_ref_map[(_norm(norm_anchor_id), _norm(target))].append(site)

        # 1) Regular call edges from reverse callers.
        for anchor in anchors.values():
            if anchor.is_virtual:
                continue
            for caller_id in anchor.callers:
                caller = _resolve_id(caller_id, id_index)
                if not caller or caller.is_virtual:
                    continue
                from_id = _norm(caller.id)
                to_id = _norm(anchor.id)
                if not _affected(from_id):
                    continue
                if (from_id, to_id) in skip_pairs:
                    continue  # callee 通过虚拟块路由，不建直接边
                refs = callee_ref_map.get((from_id, to_id), [])
                if not refs:
                    refs = [{"target": to_id, "seq": 0, "conds": ["nocond"]}]
                for ref in refs:
                    condition = _callee_condition(ref)
                    bridge_kind = ref.get("bridge_kind") if isinstance(ref, dict) else None
                    _add_edge(Edge(
                        from_id=from_id,
                        to_id=to_id,
                        edge_type="dispatch" if bridge_kind else "call",
                        data_in=", ".join(i.get("type", "") for i in anchor.inputs if i.get("type")),
                        data_out=", ".join(o.get("type", "") for o in anchor.outputs if o.get("type")),
                        outer_hash=_edge_hash(from_id, to_id),
                        condition=condition,
                        is_conditional=bool(condition),
                        seq=[_callee_seq(ref)],
                        call_line=int(ref.get("line", 0) or 0),
                        call_column=int(ref.get("column", 0) or 0),
                        resolution=str(ref.get("resolution") or "exact"),
                        evidence=str(ref.get("evidence") or "anchor-call-site"),
                        bridge_kind=bridge_kind,
                    ))

        # 2) Inheritance edges.
        for anchor in anchors.values():
            if anchor.symbol_type != "class":
                continue
            if not _affected(anchor.id):
                continue
            for parent in anchor.parent_classes:
                parent_anchor = _resolve_id(parent, id_index)
                to_id = _norm(parent_anchor.id) if parent_anchor else _norm(parent)
                _add_edge(Edge(
                    from_id=_norm(anchor.id),
                    to_id=to_id,
                    edge_type="inherit",
                    data_in="class inherit",
                    data_out="inherited methods+attrs",
                ))

        for anchor in anchors.values():
            if anchor.symbol_type == "method" and anchor.overrides:
                if not _affected(anchor.id):
                    continue
                _add_edge(Edge(
                    from_id=_norm(anchor.id),
                    to_id="override::{}".format(anchor.overrides),
                    edge_type="inherit",
                    data_in="override",
                    data_out=anchor.overrides,
                ))

        # 3) Dataflow edges: 严谨数据流 —— 只保留真实数据移动
        #    (参数传入 / 返回值被消费 / 产出 relay / 同类 self.attr 写->读)，
        #    不再"调用即数据流"。
        try:
            from analyzer.dataflow.language.python.strict_dataflow import compute_strict_dataflow

            for df in compute_strict_dataflow(str(root_path), anchors, skip_pairs=skip_pairs,
                                              only=dirty):
                if "relay" in (df.get("kinds") or []):
                    # 键必须和写进文件的那条边同口径：df 是 dataflow 提取器的
                    # 原始字典，没有 edge_type，直接拿它做键会和读回来的边对不上。
                    relay_emitters[_edge_key_text(dict(df, edge_type="dataflow"))] = \
                        str(df.get("emitter", ""))
                # 这里不能再按 from_id 过滤：`return` 边的 from 端是没改的那个
                # callee，它由 **caller** 的分析发出来，按 from 过滤会把新边丢掉。
                # 收窄已经由 only= 完成——它按"被分析的 anchor"收窄。
                _add_edge(Edge(
                    from_id=df["from_id"],
                    to_id=df["to_id"],
                    edge_type="dataflow",
                    data_in=df.get("data_in", ""),
                    data_out=df.get("data_out", ""),
                    condition=df.get("condition"),
                    is_conditional=bool(df.get("condition")),
                    seq=df.get("seq", []),
                    evidence=df.get("evidence", "strict-dataflow"),
                ))
        except Exception as ex:  # 严格提取失败时回退旧的 call-derived dataflow，保证产物可用
            failed.append("strict dataflow, fallback to call-derived: {}".format(ex))
            for anchor in anchors.values():
                if anchor.is_virtual:
                    continue
                if not _affected(anchor.id):
                    continue
                for raw_callee in _iter_call_refs(anchor):
                    callee_id = _callee_target(raw_callee)
                    if not callee_id:
                        continue
                    callee = _resolve_id(callee_id, id_index)
                    if not callee or callee.is_virtual:
                        continue
                    if (_norm(anchor.id), _norm(callee.id)) in skip_pairs:
                        continue  # callee 通过虚拟块路由，不建直接数据流边
                    condition = _callee_condition(raw_callee)
                    _add_edge(Edge(
                        from_id=_norm(anchor.id),
                        to_id=_norm(callee.id),
                        edge_type="dataflow",
                        data_in=", ".join(o.get("type", "") for o in anchor.outputs if o.get("type")),
                        data_out=", ".join(i.get("type", "") for i in callee.inputs if i.get("type")),
                        condition=condition,
                        is_conditional=bool(condition),
                        seq=[_callee_seq(raw_callee)],
                    ))

        # 4) Impact edges 见函数末尾——它是对**全部**边做扇入统计，所以必须在
        #    增量合并之后算；放在这里会让增量只看见脏集那几条边，"几个模块依赖它"
        #    就会算错。

        # 5) Dispatch edges.
        try:
            from scanner.calls.string_dispatch import find_string_dispatches

            # 增量时只扫改动过的文件：dispatch 边的 from 就在被扫的文件里，
            # 没扫到的文件上的 dispatch 边由"旧边原样搬过来"负责保留。
            for dispatch in find_string_dispatches(
                    str(root_path), only_files=changed_files):
                if not _affected(dispatch["from_id"]):
                    continue
                _add_edge(Edge(
                    from_id=dispatch["from_id"],
                    to_id=dispatch["to_id"],
                    edge_type="dispatch",
                    data_in=dispatch.get("data_in", "string route"),
                    data_out=dispatch.get("data_out", "conditional call"),
                    condition=dispatch.get("condition"),
                    dispatch_key=dispatch.get("dispatch_key"),
                    dispatch_value=dispatch.get("dispatch_value"),
                    is_conditional=dispatch.get("is_conditional", True),
                ))
        except Exception as ex:
            failed.append("dispatch edges: {}".format(ex))

        # 6) Virtual block edges:
        #    - 只建 func -> 最外层 vblock（parent 是真实函数的 vblock）
        #    - 建 vblock -> real_func（vblock 的直接真实函数 callee，供影响面反查）
        #    - 不建 vblock -> child_vblock（子块透视由 flatten_virtual 走 anchors）
        for anchor in anchors.values():
            if not anchor.is_virtual:
                continue

            # func -> outermost_vblock：仅当 parent 是非虚拟节点时才加
            if anchor.parent_anchor:
                parent = _resolve_id(anchor.parent_anchor, id_index)
                if parent and not parent.is_virtual and _affected(anchor.parent_anchor):
                    refs = callee_ref_map.get((_norm(anchor.parent_anchor), _norm(anchor.id)), [])
                    seq_list = [_callee_seq(ref) for ref in refs]
                    _add_edge(Edge(
                        from_id=_norm(anchor.parent_anchor),
                        to_id=_norm(anchor.id),
                        edge_type="call",
                        data_in="control entry",
                        data_out=anchor.virtual_kind or "virtual block",
                        scope_label=anchor.scope_label,
                        seq=seq_list,
                    ))

            # vblock -> real_func：只加真实函数 callee，跳过嵌套 vblock
            if not _affected(anchor.id):
                continue
            for raw_callee in _iter_call_refs(anchor):
                target_id = _callee_target(raw_callee)
                target_anchor = _resolve_id(target_id, id_index)
                if not target_anchor or target_anchor.is_virtual:
                    continue
                _condition = _callee_condition(raw_callee)
                _scope = raw_callee.get("scope_label") if isinstance(raw_callee, dict) else None
                _seq = _callee_seq(raw_callee)
                _add_edge(Edge(
                    from_id=_norm(anchor.id),
                    to_id=_norm(target_anchor.id),
                    edge_type="call",
                    data_in=anchor.virtual_kind or "control block",
                    data_out="conditional call" if _condition else "nested call",
                    condition=_condition,
                    is_conditional=bool(_condition),
                    scope_label=_scope,
                    seq=[_seq],
                ))

    except Exception as ex:
        failed.append("relation generation: {}".format(ex))

    merged: list[Edge] = list(edge_map.values())
    if dirty is not None:
        # 增量：只丢"产生它的那个 anchor 被重算过"的旧边，其余原样搬过来。
        # 脏边一条都不留——重算就是唯一真相，留着会让删掉的调用变成幽灵边。
        seen = {_edge_key_text(asdict(edge)) for edge in merged}
        for item in previous:
            try:
                edge = Edge(**item)
            except TypeError:
                continue
            emitter = _edge_emitter(item, relay_emitters)
            if emitter.startswith("\u0000state:"):
                stale = _norm(emitter[len("\u0000state:"):]) in dirty_classes
            elif emitter == _ALWAYS:
                stale = True
            elif emitter:
                stale = _norm(emitter) in dirty
            else:
                # emitter 不明（老索引里的 relay 边）：不丢。丢错一条没重算过的
                # 边是静默的索引漂，留错一条会在下一次全量重建时自己消失。
                stale = False
            if stale:
                continue
            key = _edge_key_text(item)
            if key in seen:
                continue          # state 段每轮全量重推，会和搬过来的旧边撞上
            seen.add(key)
            merged.append(edge)

    # 4) Impact edges：对**全部**边做扇入统计。增量重算时脏集只覆盖了一部分，
    #    所以旧的 impact 边全部丢掉，由合并后的边集重新推一遍。
    if dirty is not None:
        merged = [edge for edge in merged if edge.edge_type != "impact"]
    dependents = defaultdict(set)
    for edge in merged:
        if edge.edge_type in ("call", "dataflow"):
            dependents[edge.to_id].add(_module_of(edge.from_id))
    for to_id in sorted(dependents):
        modules = dependents[to_id]
        if len(modules) >= 2:
            merged.append(Edge(
                from_id="impact::risk",
                to_id=to_id,
                edge_type="impact",
                data_in="{} modules depend on target".format(len(modules)),
                data_out=", ".join(sorted(modules)),
            ))

    edges = merged
    by_type = dict(Counter(edge.edge_type for edge in edges))
    for name in ["call", "inherit", "dataflow", "impact", "dispatch"]:
        by_type.setdefault(name, 0)

    data = {
        "edges": [asdict(edge) for edge in edges],
        "meta": {
            "total_edges": len(edges),
            "by_type": by_type,
            "failed": failed,
            # relay 边到"谁的分析发出了它"的表。增量判断旧边要不要丢时必须知道
            # 这个，光看两端认不出来。表本身很小：只有 relay 边需要。
            "relay_emitters": {k: v for k, v in relay_emitters.items() if v},
        },
    }
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)

    return {
        "total": len(edges),
        "by_type": by_type,
        "failed": failed,
    }
