"""一个功能由哪些函数实现：从入口顺着调用边走到的全部代码。

- 虚拟块（循环、条件分支 ``file::fn#loop:…``）只是路过，它里面的调用照样往下走，
  它本身不算成员
- 走到一个类，类的方法一并算进来：``obj.method()`` 静态解析不到目标，不这样补，
  一个类的实现就只剩构造函数
- 不止一个功能用到的函数是共享底座，单独成模块，不算哪一个功能私有
"""
from collections import Counter, defaultdict

SHARED_MIN = 2


def class_methods(code):
    """{类 id: [方法 id]}：方法 id 形如 ``file::Class.method``。"""
    out = defaultdict(list)
    for aid in code:
        path, _, symbol = aid.partition("::")
        if "." in symbol:
            out["{}::{}".format(path, symbol.rsplit(".", 1)[0])].append(aid)
    return out


def reach(anchors, start, code, methods, limit=5000):
    """入口能走到的代码 anchor（含入口自己）。"""
    seen, members, stack = {start}, {start}, [start]
    while stack and len(members) < limit:
        aid = stack.pop()
        anchor = anchors.get(aid)
        if anchor is None:
            continue
        nxt = list(anchor.callees or []) + methods.get(aid, [])
        for target in nxt:
            if target in seen or target.split("#")[0] not in code:
                continue
            seen.add(target)
            stack.append(target)
            if "#" not in target:
                members.add(target)
    return members


def split_shared(closures, minimum=SHARED_MIN):
    """被 ≥minimum 个功能走到的 anchor 是共享底座。返回 (shared 集合, 每个 anchor 被几个功能用)。"""
    used_by = Counter(aid for members in closures.values() for aid in members)
    shared = {aid for aid, n in used_by.items() if n >= minimum}
    return shared, used_by


def group_entries(entries, closures, overlap=0.6):
    """实现几乎重合的入口是同一个功能（并查集）：两个闭包的交集占小的一方 ≥ overlap。"""
    parent = {e["id"]: e["id"] for e in entries}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    ids = [e["id"] for e in entries]
    owners = defaultdict(list)
    for eid in ids:
        for aid in closures[eid]:
            owners[aid].append(eid)
    pairs = Counter()
    for holders in owners.values():
        if len(holders) <= 8:
            for i, a in enumerate(holders):
                for b in holders[i + 1:]:
                    pairs[(a, b)] += 1
    for (a, b), common in pairs.items():
        if common / min(len(closures[a]), len(closures[b])) >= overlap:
            parent[find(a)] = find(b)
    groups = defaultdict(list)
    for eid in ids:
        groups[find(eid)].append(eid)
    return list(groups.values())
