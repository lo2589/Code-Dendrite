"""The MCP context tool must use the public L0/L1/L2 packet signatures."""

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path

from analyzer.anchors import generate_all_anchors


def test_mcp_context_levels_without_optional_transport(tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text(
        "def discount(total):\n    return total * 0.8\n", encoding="utf-8"
    )
    generate_all_anchors(str(tmp_path))
    (tmp_path / ".codedendrite" / "relations.json").write_text(
        json.dumps({"edges": []}), encoding="utf-8"
    )

    mcp = types.ModuleType("mcp")
    mcp.__path__ = []
    mcp_types = types.ModuleType("mcp.types")
    mcp_server = types.ModuleType("mcp.server")
    mcp_stdio = types.ModuleType("mcp.server.stdio")

    class TextContent:
        def __init__(self, *, type, text):
            self.text = text

    class Server:
        def __init__(self, name):
            pass

        def list_tools(self):
            return lambda function: function

        def call_tool(self):
            return lambda function: function

    mcp_types.TextContent = TextContent
    mcp_server.Server = Server
    mcp_stdio.stdio_server = lambda: None
    for name, module in (
        ("mcp", mcp), ("mcp.types", mcp_types),
        ("mcp.server", mcp_server), ("mcp.server.stdio", mcp_stdio),
    ):
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(sys, "argv", ["server.py", "--root", str(tmp_path)])
    server_path = Path(__file__).resolve().parents[3] / "mcp" / "server.py"
    spec = importlib.util.spec_from_file_location("codedendrite_mcp_context_test", server_path)
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)

    async def query(level):
        content = await server.call_tool("cd_context", {"query": "discount", "level": level})
        return json.loads(content[0].text)

    assert "project" in asyncio.run(query("l0"))
    assert asyncio.run(query("l1"))["task_anchor"] == "app.py::discount"
    assert asyncio.run(query("l2"))["entry"] == "app.py::discount"
