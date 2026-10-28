"""模块树 = 功能树：一个模块是一个功能，讲清它从哪进来、一步一步怎么做完。

  入口（feature_entries）→ 实现范围（feature_closure.reach）→ 按私有实现合并入口
  → 切出共享底座 → what / how（feature_describe）→ 模块间的边 → 完整性

判断两个入口是不是同一个功能，只比它们私有的那部分实现：带上共享底座比，人人都调
load_anchors，全部会被并成一个——旧模块树按"同目录 + 一条边"合并，塌成几个大杂烩，
就是这个原因。

输出沿用 module_tree_v2.json 的结构（modules / edges / summary / completeness），
HTML 页、任务上下文包照旧能读。
"""
from collections import Counter, defaultdict
from pathlib import PurePosixPath

from usage.path_policy import classify_path_role
from usage.structure.module_tree_v2.feature_closure import class_methods, group_entries, reach, split_shared
from usage.structure.module_tree_v2.feature_describe import (
    describe_how, describe_what, doc_of, feature_name, ordered_steps,
)
from usage.structure.module_tree_v2.feature_entries import code_ids, find_entries

TINY = 1            # 私有实现只有自己（下面全是共享底座）的根入口：一层薄包装，算零散代码
_KIND_RANK = {"script": 0, "registered": 1, "root": 2}
_KIND_LABEL = {"script": "脚本入口 __main__", "registered": "注册入口", "root": "调用图的根"}


def _dir(path):
    return str(PurePosixPath(path).parent)


def _package(path, depth=3):
    """共享底座按包归组（src/analyzer/anchors），零散入口按层（src/usage）：按最深目录分，
    src/analyzer/dataflow/language/python/analyzer 这种各成一块，卡片多到没法读。"""
    parts = PurePosixPath(path).parent.parts
    return "/".join(parts[:depth]) or "."


def _test_callers(anchors, policy):
    """{anchor: [调用它的测试]}：测试文件里的调用者。"""
    out = defaultdict(list)
    for aid, a in anchors.items():
        # 测试函数里的 try / loop 块（test_x#try:285:2）不是另一个测试
        if "#" in aid or classify_path_role(a.file, policy) != "reference_only":
            continue
        for callee in a.callees or []:
            out[callee.split("#")[0]].append(aid)
    return out


def _confidence(has_doc, has_tests, size):
    if size >= 3 and has_doc and has_tests:
        return "A"
    if size >= 3 and (has_doc or has_tests):
        return "B"
    return "C" if size >= 3 else "D"


class _Builder:
    def __init__(self, root, anchors, policy):
        self.root, self.anchors, self.policy = root, anchors, policy
        self.code = code_ids(anchors, policy)
        self.methods = class_methods(self.code)
        self._reach = {}
        self.tests = _test_callers(anchors, policy)

    def reach(self, aid):
        if aid not in self._reach:
            self._reach[aid] = reach(self.anchors, aid, self.code, self.methods)
        return self._reach[aid]

    def feature(self, group, members, shared, by_id):
        lead = min(group, key=lambda e: (_KIND_RANK[by_id[e]["kind"]], -len(self.reach(e)), e))
        entry = by_id[lead]
        own = members - shared
        steps = ordered_steps(self.anchors, lead, members)
        own_reach = {sid: len(self.reach(sid) - shared) for sid in members & set(
            t for s in steps for t in [s] + ordered_steps(self.anchors, s, members))}
        files = Counter(self.anchors[a].file for a in own)
        tests = sorted({t for a in own for t in self.tests.get(a, [])})
        has_doc = bool(doc_of(self.root, self.anchors[lead]))
        used_shared = sorted({_package(self.anchors[a].file) for a in members & shared})
        status = "core_flow" if entry["kind"] != "root" else "independent_capability"
        return {
            "name": feature_name(self.anchors, entry),
            "what": describe_what(self.root, self.anchors, lead, members),
            "how": describe_how(self.root, self.anchors, lead, members, own_reach, shared),
            "role": "入口：{}（{}）。私有实现 {} 个函数、{} 个文件{}".format(
                _KIND_LABEL[entry["kind"]], lead, len(own), len(files),
                "；用到共享底座：" + "、".join(used_shared[:4]) if used_shared else ""),
            "functions": [lead] + steps[:7],
            "entrypoints": sorted(group),
            "files": [f for f, _ in files.most_common()],
            "status": status,
            "confidence": _confidence(has_doc, bool(tests), len(own)),
            "evidence": {"entrypoints": sorted(group), "tests": tests[:12], "docs": [lead] if has_doc else [],
                         "classes": sorted(a for a in own if self.anchors[a].symbol_type == "class")[:12],
                         "relations": [len(own)], "directories": sorted({_dir(f) for f in files})},
            "risks": [] if has_doc else ["entry_has_no_docstring"],
            "_members": own,
        }

    def shared_module(self, directory, ids, used_by):
        ranked = sorted(ids, key=lambda a: (-used_by[a], a))
        lines = []
        for i, aid in enumerate(ranked[:8], 1):
            a = self.anchors[aid]
            doc = doc_of(self.root, a) or (a.signature or a.symbol)
            lines.append("{}. {} — {}  [{}:{}] · 被 {} 个功能用".format(i, a.symbol, doc, a.file, a.line_start, used_by[aid]))
        if len(ranked) > 8:
            lines.append("… 另外 {} 个函数".format(len(ranked) - 8))
        return {
            "name": "共享底座 · " + directory,
            "what": "被多个功能共用的 {} 个函数，最常用的是 {}".format(len(ids), self.anchors[ranked[0]].symbol),
            "how": "\n".join(lines), "role": "共享底座：不止一个功能会走到这里",
            "functions": ranked[:8], "entrypoints": [], "files": sorted({self.anchors[a].file for a in ids}),
            "status": "support_utility", "confidence": "B" if any(self.tests.get(a) for a in ids) else "C",
            "evidence": {"entrypoints": [], "tests": sorted({t for a in ids for t in self.tests.get(a, [])})[:12],
                         "docs": [], "classes": [], "relations": [len(ids)], "directories": [directory]},
            "risks": [], "_members": set(ids),
        }

    def dormant_module(self, directory, entry_ids, members):
        names = [self.anchors[e].symbol for e in sorted(entry_ids)]
        return {
            "name": "零散入口 · " + directory,
            "what": "没接进任何功能的 {} 个函数：没人调用它们，或者只被同样没接进来的代码调用（可能是死代码、动态调用或尚未接线）".format(len(entry_ids)),
            "how": "\n".join("· {}  [{}:{}]".format(self.anchors[e].symbol, self.anchors[e].file, self.anchors[e].line_start)
                             for e in sorted(entry_ids)[:12]) + ("\n… 另外 {} 个".format(len(names) - 12) if len(names) > 12 else ""),
            "role": "待确认：静态分析找不到它们的调用者", "functions": sorted(entry_ids)[:8],
            "entrypoints": sorted(entry_ids), "files": sorted({self.anchors[a].file for a in members}),
            "status": "dormant", "confidence": "D",
            "evidence": {"entrypoints": sorted(entry_ids), "tests": [], "docs": [], "classes": [], "relations": [],
                         "directories": [directory]},
            "risks": ["possible_dead_code"], "_members": set(members),
        }


def _edges(modules, anchors):
    owner = {}
    for mod in modules:
        for aid in mod["_members"]:
            owner.setdefault(aid, mod["id"])
    counts = Counter()
    for mod in modules:
        for aid in mod["_members"]:
            for callee in anchors[aid].callees or []:
                target = owner.get(callee.split("#")[0])
                if target and target != mod["id"]:
                    counts[(mod["id"], target)] += 1
    return [{"from": f, "to": t, "edge_type": "call", "weight": w} for (f, t), w in counts.most_common()]


def _completeness(modules, code, anchors, reached):
    live = set()
    for mod in modules:
        if mod["status"] != "dormant":
            live |= mod["_members"]
    areas = {_dir(anchors[a].file) for a in code}
    covered = {_dir(anchors[a].file) for a in live}
    return {
        "area_coverage": {"total_areas": len(areas), "covered": len(covered & areas), "uncovered": sorted(areas - covered)},
        "function_coverage": {"total": len(code), "in_features": len(live), "unreached": len(code - reached)},
        "fake_module_warnings": [{"module_id": m["id"], "name": m["name"], "reason": "没有调用者，也没接进任何功能"}
                                 for m in modules if m["status"] == "dormant"],
        "low_confidence_modules": [{"module_id": m["id"], "name": m["name"], "confidence": m["confidence"]}
                                   for m in modules if m["confidence"] in ("C", "D")],
        "missing_evidence": [{"module_id": m["id"], "name": m["name"], "missing": ["tests"]}
                             for m in modules if m["status"] in ("core_flow", "independent_capability") and not m["evidence"]["tests"]],
    }


def build_feature_tree(root, anchors, policy):
    b = _Builder(root, anchors, policy)
    entries = find_entries(anchors, b.code)
    by_id = {e["id"]: e for e in entries}
    closures = {e["id"]: b.reach(e["id"]) for e in entries}
    shared0, _ = split_shared(closures)
    groups = group_entries(entries, {k: v - shared0 for k, v in closures.items()})
    members = [set().union(*(closures[e] for e in g)) for g in groups]
    shared, used_by = split_shared(dict(enumerate(members)))

    features, tiny = [], defaultdict(lambda: (set(), set()))
    for group, mem in zip(groups, members):
        lead_kind = min(_KIND_RANK[by_id[e]["kind"]] for e in group)
        if lead_kind == _KIND_RANK["root"] and len(mem - shared) <= TINY:
            bucket = tiny[_package(anchors[group[0]].file, 2)]
            bucket[0].update(group); bucket[1].update(mem - shared)
            continue
        features.append(b.feature(group, mem, shared, by_id))
    features.sort(key=lambda m: (m["status"] != "core_flow", -len(m["_members"]), m["name"]))
    shared_by_dir = defaultdict(list)
    for aid in shared:
        shared_by_dir[_package(anchors[aid].file)].append(aid)
    support = sorted((b.shared_module(d, ids, used_by) for d, ids in shared_by_dir.items()), key=lambda m: -len(m["_members"]))
    # 任何功能都走不到的函数也是零散代码：没人调、自己也不往下调的那种，入口识别看不见它们
    reached_all = set().union(*members) if members else set()
    for aid in b.code - reached_all:
        if anchors[aid].symbol_type in ("function", "class"):
            bucket = tiny[_package(anchors[aid].file, 2)]
            bucket[0].add(aid); bucket[1].add(aid)
    dormant = [b.dormant_module(d, e, m) for d, (e, m) in sorted(tiny.items())]

    modules = features + support + dormant
    for i, mod in enumerate(modules, 1):
        mod["id"] = "M{:03d}".format(i)
    reached = set().union(*members) if members else set()
    tree = {
        "version": "module_tree_v2",
        "kind": "features",
        "modules": modules,
        "edges": _edges(modules, anchors),
        "summary": {
            "total_modules": len(modules),
            "features": len(features), "shared": len(support), "dormant": len(dormant),
            "by_status": dict(Counter(m["status"] for m in modules)),
            "by_confidence": dict(Counter(m["confidence"] for m in modules)),
        },
        "completeness": _completeness(modules, b.code, anchors, reached),
    }
    for mod in modules:
        mod["size"] = {"functions": len(mod.pop("_members")), "files": len(mod["files"])}
    return tree
