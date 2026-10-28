"""把一个功能说清楚：它做什么（what）、怎么实现（how）。

what 取入口的文档字符串第一句；``__main__`` 取所在文件的模块文档字符串。
how 是入口按调用顺序调到的每一步：函数名 · 它的文档字符串第一句 · 文件:行 · 往下还连着
多少个函数。这样读模块树就是读"这个功能怎么一步一步做完的"，不是一个文件清单。

文档字符串现场从源码读（索引里没存），只读 Python；其它语言退回函数签名。
"""
import ast
from functools import lru_cache
from pathlib import Path

MAX_STEPS = 8


@lru_cache(maxsize=None)
def _docstrings(root, rel_path):
    """{定义所在行: 文档字符串第一句}，0 号放模块文档字符串。"""
    path = Path(root) / rel_path
    if path.suffix != ".py":
        return {}
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return {}
    out = {}
    for node in [tree] + [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]:
        doc = ast.get_docstring(node)
        if doc:
            first = doc.strip().split("\n")[0].strip().rstrip("。.")
            line = 0 if isinstance(node, ast.Module) else min(
                [node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
            out[line] = first[:120]
            if not isinstance(node, ast.Module):
                out[node.lineno] = first[:120]
    return out


def doc_of(root, anchor):
    """anchor 的文档字符串第一句；没有就是空串。"""
    docs = _docstrings(str(root), anchor.file)
    if anchor.symbol_type == "entrypoint":
        return docs.get(0, "")
    try:
        return docs.get(int(anchor.line_start), "")
    except (TypeError, ValueError):
        return ""


def _line(anchor):
    try:
        return int(anchor.line_start)
    except (TypeError, ValueError):
        return 0


def _sites(anchors, entry_id):
    return sorted((s for s in anchors[entry_id].call_sites or [] if isinstance(s, dict)),
                  key=lambda s: (s.get("seq", 0), s.get("line", 0)))


def ordered_steps(anchors, entry_id, members):
    """入口按调用先后（call_sites 的 seq）直接调到的、在实现范围内的函数，去重。"""
    out = []
    for site in _sites(anchors, entry_id):
        target = str(site.get("target") or "")
        if target in members and target != entry_id and target not in out:
            out.append(target)
    return out


_COND_WORDS = {"if": "若", "elif": "否则若", "else": "否则", "for": "循环", "while": "循环", "with": "在", "except": "出错时"}


def step_condition(anchors, entry_id, target):
    """这一步在什么条件下发生：最内层的 if / for / while（跳过 try）。没有条件返回空串。"""
    for site in _sites(anchors, entry_id):
        if site.get("target") != target:
            continue
        for cond in reversed(site.get("conds") or []):
            if not isinstance(cond, dict):
                continue
            (key, text), = list(cond.items())[:1] or [("", "")]
            kind = str(key).split(":")[0]
            if kind in ("try", "finally"):
                continue
            word = _COND_WORDS.get(kind, kind)
            return "{} {}".format(word, str(text)[:60]).strip() if kind != "else" else word
        return ""
    return ""


def _step_line(root, anchors, caller, sid, number, own_reach, shared):
    a = anchors[sid]
    doc = doc_of(root, a) or (a.signature or a.symbol)
    tail = "共享底座" if sid in shared else "往下 {} 个本功能的函数".format(max(own_reach.get(sid, 1) - 1, 0))
    cond = step_condition(anchors, caller, sid)
    return "{} {}{} — {}  [{}:{}] · {}".format(number, "〔{}〕".format(cond) if cond else "", a.symbol, doc, a.file, _line(a), tail)


def describe_how(root, anchors, entry_id, members, own_reach, shared, depth=0, prefix=""):
    """how：入口按调用顺序走过的每一步。某一步是唯一的一步（__main__ → main）时往下展开它，最多两层。"""
    steps = ordered_steps(anchors, entry_id, members)
    lines = []
    for i, sid in enumerate(steps[:MAX_STEPS], 1):
        number = "{}{}.".format(prefix, i)
        lines.append("  " * depth + _step_line(root, anchors, entry_id, sid, number, own_reach, shared))
        if len(steps) == 1 and depth < 2 and sid not in shared:
            lines.extend(describe_how(root, anchors, sid, members, own_reach, shared, depth + 1, number).split("\n"))
    if len(steps) > MAX_STEPS:
        lines.append("  " * depth + "… 另外 {} 步".format(len(steps) - MAX_STEPS))
    if not lines and depth == 0:
        a = anchors[entry_id]
        lines.append("入口自己完成，不再往下调用  [{}:{}]".format(a.file, _line(a)))
    return "\n".join(l for l in lines if l.strip())


def describe_what(root, anchors, entry_id, members):
    """入口的文档字符串；没有就退到所在文件的模块说明，再退到第一步函数的说明。"""
    a = anchors[entry_id]
    doc = doc_of(root, a) or _docstrings(str(root), a.file).get(0, "")
    if doc:
        return doc
    node, steps = entry_id, ordered_steps(anchors, entry_id, members)
    for _ in range(2):              # __main__ → main → 真正分叉的地方
        if len(steps) != 1:
            break
        node = steps[0]
        doc = doc_of(root, anchors[node])
        if doc:
            return doc
        steps = ordered_steps(anchors, node, members)
    if not steps:
        return "{}（没有文档字符串，也不再往下调用）".format(a.signature or a.symbol)
    branched = any(step_condition(anchors, node, t) for t in steps)
    names = "、".join(anchors[t].symbol for t in steps[:4]) + (" 等 {} 步".format(len(steps)) if len(steps) > 4 else "")
    return "{}{}（没有文档字符串，按调用推断）".format("按条件调用 " if branched else "依次调用 ", names)


def _module_path(rel_path):
    """src/usage/cli/ensure_path.py → usage/cli/ensure_path：文件名单看会误导（ensure_path 其实是整个 CLI 的分发入口）。"""
    parts = list(Path(rel_path).with_suffix("").parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    if parts and parts[-1] in ("__main__", "__init__"):
        parts = parts[:-1] or parts
    return "/".join(parts)


def feature_name(anchors, entry):
    a = anchors[entry["id"]]
    if entry["kind"] == "script":
        return _module_path(a.file)
    where = "/".join(_module_path(a.file).split("/")[-2:])
    if entry["kind"] == "registered":
        return "{} · @{} · {}".format(a.symbol, entry["label"].split("(")[0], where)
    return "{} · {}".format(a.symbol, where)
