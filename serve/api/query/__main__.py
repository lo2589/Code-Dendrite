"""python -m serve.api.query 的入口。

命令分发写在 cmd_chain.py 的 __main__ 块里（拆分时随尾部代码落在那一块）。
这里按文件路径执行它，避免重复搬运 100 行分发逻辑。
"""
import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("cmd_chain.py")), run_name="__main__")
