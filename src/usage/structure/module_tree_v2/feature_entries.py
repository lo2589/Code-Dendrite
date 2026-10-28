"""功能从哪里开始：入口。

模块树的一个模块就是一个功能，功能从外面能触发它的地方开始：

- script：``if __name__ == "__main__"``（anchor 类型 entrypoint）
- registered：带注册装饰器的函数，例如 MCP 的 ``@app.call_tool()``
- root：正常代码里没有任何调用者、自己又往下调用的函数或类——调用图的根

方法不当入口：``obj.method()`` 这种属性调用静态解析不到目标，方法因此看起来"没人调"，
当入口会冒出成百上千个假功能。走到一个类时，它的方法算进实现（见 feature_closure）。
"""
from usage.path_policy import classify_path_role

CODE_TYPES = {"function", "method", "class", "entrypoint"}
# 测试框架和语言自带的装饰器不算对外注册：@property 的方法不是入口
_TEST_DECORATORS = ("pytest.", "unittest.", "mock.")
_BUILTIN_DECORATORS = {
    "property", "staticmethod", "classmethod", "abstractmethod", "cached_property", "dataclass",
    "contextmanager", "asynccontextmanager", "wraps", "lru_cache", "cache", "overload",
    "total_ordering", "singledispatch", "setter", "getter", "deleter", "override", "final",
}


def _is_builtin(text):
    head = text.split("(")[0]
    return head.split(".")[-1] in _BUILTIN_DECORATORS


def code_ids(anchors, policy):
    """正常代码里的可调用 anchor（不含测试、虚拟块、CSS/DOM）。"""
    return {aid for aid, a in anchors.items()
            if a.symbol_type in CODE_TYPES and "#" not in aid
            and classify_path_role(a.file, policy) == "normal"}


def _decorator_text(item):
    """装饰器有的存成字符串 ``app.call_tool()``，有的存成 ``{key, name}``。"""
    if isinstance(item, dict):
        name, key = item.get("name") or "", item.get("key") or ""
        return "{}({!r})".format(name, key) if key else str(name)
    return str(item)


def _decorators(anchor):
    meta = anchor.block_metadata if isinstance(anchor.block_metadata, dict) else {}
    texts = [_decorator_text(d) for d in meta.get("decorators") or []]
    return [t for t in texts if t and not t.startswith(_TEST_DECORATORS) and not _is_builtin(t)]


def _code_callers(anchor, code):
    return [c for c in anchor.callers or [] if c.split("#")[0] in code]


def _code_callees(anchor, code):
    return [c for c in anchor.callees or [] if c.split("#")[0] in code]


def find_entries(anchors, code):
    """返回 [{id, kind, label}]，kind 是 script / registered / root。"""
    entries = []
    for aid in sorted(code):
        a = anchors[aid]
        if not _code_callees(a, code) and a.symbol_type != "class":
            continue
        if a.symbol_type == "entrypoint":
            entries.append({"id": aid, "kind": "script", "label": "__main__"})
        elif _decorators(a):
            entries.append({"id": aid, "kind": "registered", "label": _decorators(a)[0]})
        elif a.symbol_type in ("function", "class") and not _code_callers(a, code) \
                and not a.symbol.startswith("__"):
            if a.symbol_type == "class" and not any(m.startswith(aid + ".") for m in code):
                continue
            entries.append({"id": aid, "kind": "root", "label": a.symbol_type})
    return entries
