"""import 解析：照 Python 那套——import 把"名字→来源模块"钉死，模块再映射到仓库文件。
让跨文件、重名、模块限定的调用都能 O(1) 解到正确目标。

每文件输出两张表：
  names   : from Y import f [as g]  -> {本地名: 目标anchor_id}（含追 __init__ re-export 链）
  modules : import X [as m]         -> {本地名: 模块文件rel}（供 m.f() 解析）
"""
from pathlib import Path as _Path


def _module_to_file_index(anchor_files) -> dict:
    """{点路径模块: 文件rel}。sympy/core/add.py -> sympy.core.add；
    sympy/core/__init__.py -> sympy.core。"""
    idx = {}
    for f in anchor_files:
        f = str(f).replace("\\", "/")
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


def build_import_resolution(import_anchors, anchor_files, root=None, anchor_ids=None) -> dict:
    """返回 {导入方文件rel: {"names": {本地名: 目标id或None}, "modules": {本地名: 模块文件rel}}}。"""
    anchor_ids = anchor_ids or set()

    def _rel(fp):
        fp = str(fp).replace("\\", "/")
        if root is not None:
            try:
                return str(_Path(fp).relative_to(root)).replace("\\", "/")
            except ValueError:
                pass
        return fp

    # 模块索引要含【只有 import 的 __init__.py】这类文件（无代码 anchor，但要能被 from pkg import 解析）
    all_files = {str(f).replace("\\", "/") for f in anchor_files}
    for ia in import_anchors:
        rf = _rel(getattr(ia, "file", ""))
        if rf:
            all_files.add(rf)
    mod_index = _module_to_file_index(all_files)

    # 第一遍：每文件 local -> 记录
    raw: dict = {}
    for ia in import_anchors:
        f = _rel(getattr(ia, "file", ""))
        if not f:
            continue
        meta = getattr(ia, "metadata", None) or {}
        local = meta.get("local") or getattr(ia, "name", "")
        if not local:
            continue
        kind = meta.get("import_kind") or ("from" if meta.get("from_module") else "import")
        m = raw.setdefault(f, {})
        if kind == "from":
            module = meta.get("module") or meta.get("from_module") or ""
            level = int(meta.get("level") or 0)
            orig = meta.get("orig") or local
            mod = _resolve_module(module, level, f)
            tgt_file = mod_index.get(mod)
            if tgt_file:
                m[local] = {"kind": "sym", "tgt_file": tgt_file, "orig": orig}
            else:
                sub = mod_index.get((mod + "." + orig) if mod else orig)  # from pkg import submod
                m[local] = {"kind": "mod", "modfile": sub} if sub else {"kind": "ext"}
        else:  # import X[.Y] [as Z]
            module = meta.get("module") or ""
            modfile = mod_index.get(module) or (mod_index.get(module.split(".")[0]) if module else None)
            m[local] = {"kind": "mod", "modfile": modfile} if modfile else {"kind": "ext"}

    # 第二遍：sym 目标若在目标文件里仍是 import（re-export），追到真定义
    def chase(tgt_file, name, seen):
        tid = "{}::{}".format(tgt_file, name)
        if tid in anchor_ids:
            return tid
        rec = raw.get(tgt_file, {}).get(name)
        if rec and rec.get("kind") == "sym" and (tgt_file, name) not in seen:
            seen.add((tgt_file, name))
            return chase(rec["tgt_file"], rec["orig"], seen)
        return tid if tid in anchor_ids else None

    result: dict = {}
    for f, m in raw.items():
        rf = result.setdefault(f, {"names": {}, "modules": {}})
        for local, rec in m.items():
            k = rec.get("kind")
            if k == "sym":
                rf["names"][local] = chase(rec["tgt_file"], rec["orig"], set())
            elif k == "mod" and rec.get("modfile"):
                rf["modules"][local] = rec["modfile"]
    return result
