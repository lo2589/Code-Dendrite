"""import 解析：照 Python 那套——import 把"名字→来源模块"钉死，模块再映射到仓库文件。
让跨文件、重名的调用(sympy 里 sqrt/eval 满仓库)能 O(1) 解到正确的那个，而不是丢边。

只解【from Y import f; f()】这类（call-site 记的是裸名 f，能查 import 表）。
【import X; X.f()】call-site 丢了 X 前缀，暂不解。
"""


def _module_to_file_index(anchor_files) -> dict:
    """{点路径模块: 文件rel}。sympy/core/add.py -> sympy.core.add;
    sympy/core/__init__.py -> sympy.core。"""
    idx = {}
    for f in anchor_files:
        f = f.replace("\\", "/")
        if not f.endswith(".py"):
            continue
        rel = f[:-3]
        if rel.endswith("/__init__"):
            mod = rel[: -len("/__init__")].replace("/", ".")
        elif rel == "__init__":
            mod = ""
        else:
            mod = rel.replace("/", ".")
        if mod:
            idx[mod] = f
    return idx


def _resolve_module(module: str, level: int, importing_file: str) -> str:
    """相对 import 用导入方文件的包路径拼出绝对点路径。"""
    if level and level > 0:
        pkg = importing_file.replace("\\", "/").split("/")[:-1]   # 去掉文件名 = 包目录
        up = level - 1
        base = pkg[: len(pkg) - up] if up <= len(pkg) else []
        full = base + (module.split(".") if module else [])
        return ".".join([p for p in full if p])
    return module


def build_import_resolution(import_anchors, anchor_files, root=None) -> dict:
    """返回 {导入方文件rel: {本地名: 目标anchor_id 或 None}}。
    目标在仓库里 -> '文件rel::原名'；外部/解不出 -> None（调用端据此不再瞎猜唯一名）。
    root: import 锚点的 file 是绝对路径，要转成和最终 anchor 一致的 root-相对。"""
    from pathlib import Path as _Path
    mod_index = _module_to_file_index(anchor_files)

    def _rel(fp):
        fp = str(fp).replace("\\", "/")
        if root is not None:
            try:
                return str(_Path(fp).relative_to(root)).replace("\\", "/")
            except ValueError:
                pass
        return fp

    result: dict = {}
    for ia in import_anchors:
        f = _rel(getattr(ia, "file", ""))
        if not f:
            continue
        meta = getattr(ia, "metadata", None) or {}
        local = meta.get("local") or getattr(ia, "name", "")
        if not local:
            continue
        kind = meta.get("import_kind") or ("from" if meta.get("from_module") else "import")
        m = result.setdefault(f, {})
        if kind == "from":
            module = meta.get("module") or meta.get("from_module") or ""
            level = int(meta.get("level") or 0)
            orig = meta.get("orig") or local
            mod = _resolve_module(module, level, f)
            tgt_file = mod_index.get(mod)
            if tgt_file:
                m[local] = "{}::{}".format(tgt_file, orig)     # from Y import f -> Yfile::f
            else:
                sub = mod_index.get((mod + "." + orig) if mod else orig)   # from pkg import submod
                m[local] = "{}::__module__".format(sub) if sub else None
        # 'import X' 暂不解（call-site 丢了 X. 前缀）
    return result
