"""cdd_mcp/server.py 自己把 src/ 放上 sys.path：不设 PYTHONPATH 也能导入各层包。"""
import ast
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SERVER = REPO / "src" / "cdd_mcp" / "server.py"


def _imports_mcp(node: ast.stmt) -> bool:
    if isinstance(node, ast.Import):
        return any(alias.name.split(".")[0] == "mcp" for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return (node.module or "").split(".")[0] == "mcp"
    return False


def _path_setup_source() -> str:
    """server.py 里 `import mcp` 之前的全部语句——不需要装 mcp 包就能执行。"""
    head = []
    for node in ast.parse(SERVER.read_text(encoding="utf-8")).body:
        if _imports_mcp(node):
            break
        head.append(node)
    return ast.unparse(ast.Module(body=head, type_ignores=[]))


def test_server_path_setup_makes_layer_packages_importable(tmp_path):
    probe = (
        f"exec(compile({_path_setup_source()!r}, {str(SERVER)!r}, 'exec'),"
        f" {{'__file__': {str(SERVER)!r}, '__name__': 'probe'}})\n"
        "import analyzer.anchors\n"
        "import usage.packets.task_context_packet\n"
        "print('ok')\n"
    )
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=tmp_path, env=env,
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
