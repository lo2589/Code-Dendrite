"""扫描时一律跳过的目录：唯一一份名单，所有遍历入口都用它。

以前每个扫描入口各写一份，彼此不一致：language/__init__ 和 base 跳过 build/dist，
Python 解析器却没有。于是 ``pip install .`` 留下的 build/lib/（整份源码的拷贝）被
Python 解析器扫进索引，同一个模块出现两份，``from analyzer.anchors import ...``
解析不出唯一目标——实测本仓库 ``cdd chain mcp/server.py::call_tool`` 从 55 行掉到 15 行，
所有跨文件的边全断。任何用户在自己项目里 pip install 过一次就会撞上。
"""

SKIP_DIRS = frozenset({
    "__pycache__", "node_modules", "venv", "env", "vendor",
    "target", "build", "dist", "out",
})


# 建索引走的是 CodeDendriteIgnore.should_scan，不看上面那份名单，只认项目自己的
# .codedendrite_ignore——而用户的配置里几乎不会写 build/lib。所以构建和依赖产物在
# should_scan 里先挡掉，不管项目怎么配。
#
# 不能一刀切跳过所有 build/：很多项目的 build/ 是自己的构建脚本（源码）。只认
# setuptools 产物的形状：build/lib*、build/bdist*、build/temp*。
_ARTIFACT_PARTS = frozenset({"dist", "node_modules", "site-packages", "__pycache__", "venv", ".venv"})
_BUILD_OUTPUT_PREFIXES = ("lib", "bdist", "temp")


def is_build_artifact(rel_path: str) -> bool:
    """相对路径落在构建 / 依赖产物里：pip install 留下的源码拷贝、打包输出、依赖、虚拟环境。"""
    parts = [p for p in rel_path.replace("\\", "/").split("/") if p]
    dirs = parts[:-1]
    for i, part in enumerate(dirs):
        if part in _ARTIFACT_PARTS or part.endswith(".egg-info"):
            return True
        if part == "build" and i + 1 < len(dirs) and dirs[i + 1].startswith(_BUILD_OUTPUT_PREFIXES):
            return True
    return False


def keep_dir(name: str) -> bool:
    """这个目录要不要往下扫：点开头的、构建产物、依赖目录、*.egg-info 都不扫。"""
    return not name.startswith(".") and name not in SKIP_DIRS and not name.endswith(".egg-info")
