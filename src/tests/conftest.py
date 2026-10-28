"""测试开始前，保证仓库自己的索引在。

test_task_context_smoke、test_module_tree_v2_smoke 读的是本仓库的 .codedendrite/
（anchors.json、relations.json、模块树）。索引不进 git：新克隆的仓库里没有，
这两个文件 39 个用例在 setUp 就报 FileNotFoundError——只有先手动跑过 cdd rebuild
的机器上才会绿。这里在整场测试开始前检查一次：没有就用 cdd update 建，有就不动。
"""
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CDD = REPO_ROOT / "src" / "usage" / "cli" / "cdd"


def _index_ready(root: Path) -> bool:
    data = root / ".codedendrite"
    return (data / "anchors.json").exists() and (data / "relations.json").exists()


@pytest.fixture(scope="session", autouse=True)
def repo_index():
    """没有索引就建一次；建不出来就让整场失败，并把原因说清楚。"""
    if _index_ready(REPO_ROOT):
        return
    result = subprocess.run(
        [sys.executable, str(CDD), "update", str(REPO_ROOT)],
        cwd=str(REPO_ROOT), capture_output=True, text=True, check=False,
    )
    if result.returncode != 0 or not _index_ready(REPO_ROOT):
        pytest.fail("建仓库索引失败（cdd update）：\n" + (result.stderr or result.stdout)[-2000:])
