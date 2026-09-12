"""可安装入口：把同目录的人用 CLI 装成 `cdd` 命令。

实体是 ``src/usage/cli/cdd`` —— 它**故意没有 .py 后缀**：既是 shell 里直接执行
的文件（走 shebang），也是打包时被加密进 wheel 的实体
（``pypi/build_protected_wheel.py`` → ``_human_cli.py.cdd``）。所以这里按路径用
runpy 执行它，而不是把它改成模块：改成 ``cdd.py`` 会让上面两条路一起断。

入口点写在 pyproject 的 ``[project.scripts]``：``cdd = "usage.cli.human:main"``。
"""

from __future__ import annotations

import runpy
from pathlib import Path


def _load_cli() -> dict:
    """按路径执行 CLI 脚本，返回它的命名空间（不触发 ``__main__`` 分支）。"""
    script = Path(__file__).with_name("cdd")
    if not script.exists():
        raise FileNotFoundError(f"找不到人用 CLI 实体：{script}")
    return runpy.run_path(str(script), run_name="codedendrite_human_cli")


def main(argv: list[str] | None = None) -> int:
    return _load_cli()["main"](argv)
