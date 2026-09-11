from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from io import StringIO
from contextlib import redirect_stdout

from synth.api.module_tree import (
    find_module_for_symbol,
    generate_module_summary,
    generate_module_tree,
    get_module,
    load_summary_cache,
    query_modules,
)
from serve.api.cli import module_query
from synth.context_builder.builder import ContextBuilder


def _write_fixture(root: Path) -> None:
    codedendrite = root / ".codedendrite"
    codedendrite.mkdir(parents=True, exist_ok=True)

    anchors = {
        "api/cli.py::debug_loop": {
            "id": "api/cli.py::debug_loop",
            "symbol": "debug_loop",
            "file": "api/cli.py",
            "line_start": 1,
            "line_end": 20,
            "hash": "a1",
            "code": "",
            "callers": [],
            "callees": ["run_debug_loop"],
            "inputs": [],
            "outputs": [],
            "parent_classes": [],
            "overrides": None,
            "overridden_by": [],
            "mro": [],
            "observations": [],
            "language": "python",
            "symbol_type": "function",
            "description": "",
            "drift": "ok",
        },
        "api/workflow.py::run_debug_loop": {
            "id": "api/workflow.py::run_debug_loop",
            "symbol": "run_debug_loop",
            "file": "api/workflow.py",
            "line_start": 1,
            "line_end": 40,
            "hash": "a2",
            "code": "",
            "callers": ["debug_loop"],
            "callees": ["locate_bug", "verify_fix"],
            "inputs": [],
            "outputs": [],
            "parent_classes": [],
            "overrides": None,
            "overridden_by": [],
            "mro": [],
            "observations": [],
            "language": "python",
            "symbol_type": "function",
            "description": "",
            "drift": "ok",
        },
        "api/workflow.py::locate_bug": {
            "id": "api/workflow.py::locate_bug",
            "symbol": "locate_bug",
            "file": "api/workflow.py",
            "line_start": 41,
            "line_end": 90,
            "hash": "a3",
            "code": "",
            "callers": ["run_debug_loop"],
            "callees": [],
            "inputs": [],
            "outputs": [],
            "parent_classes": [],
            "overrides": None,
            "overridden_by": [],
            "mro": [],
            "observations": [],
            "language": "python",
            "symbol_type": "function",
            "description": "",
            "drift": "ok",
        },
        "api/workflow.py::verify_fix": {
            "id": "api/workflow.py::verify_fix",
            "symbol": "verify_fix",
            "file": "api/workflow.py",
            "line_start": 91,
            "line_end": 140,
            "hash": "a4",
            "code": "",
            "callers": ["run_debug_loop"],
            "callees": [],
            "inputs": [],
            "outputs": [],
            "parent_classes": [],
            "overrides": None,
            "overridden_by": [],
            "mro": [],
            "observations": [],
            "language": "python",
            "symbol_type": "function",
            "description": "",
            "drift": "ok",
        },
        "backend/main.py::LLMSchedulerServer.handle_request": {
            "id": "backend/main.py::LLMSchedulerServer.handle_request",
            "symbol": "LLMSchedulerServer.handle_request",
            "file": "backend/main.py",
            "line_start": 200,
            "line_end": 260,
            "hash": "a5",
            "code": "",
            "callers": [],
            "callees": ["LLMSchedulerServer._handle_chat_with_model", "LLMSchedulerServer._handle_get_balance"],
            "inputs": [],
            "outputs": [],
            "parent_classes": [],
            "overrides": None,
            "overridden_by": [],
            "mro": [],
            "observations": [],
            "language": "python",
            "symbol_type": "method",
            "description": "",
            "drift": "ok",
        },
        "backend/main.py::LLMSchedulerServer._handle_chat_with_model": {
            "id": "backend/main.py::LLMSchedulerServer._handle_chat_with_model",
            "symbol": "LLMSchedulerServer._handle_chat_with_model",
            "file": "backend/main.py",
            "line_start": 261,
            "line_end": 320,
            "hash": "a6",
            "code": "",
            "callers": ["LLMSchedulerServer.handle_request"],
            "callees": [],
            "inputs": [],
            "outputs": [],
            "parent_classes": [],
            "overrides": None,
            "overridden_by": [],
            "mro": [],
            "observations": [],
            "language": "python",
            "symbol_type": "method",
            "description": "",
            "drift": "ok",
        },
        "backend/main.py::LLMSchedulerServer._handle_get_balance": {
            "id": "backend/main.py::LLMSchedulerServer._handle_get_balance",
            "symbol": "LLMSchedulerServer._handle_get_balance",
            "file": "backend/main.py",
            "line_start": 321,
            "line_end": 360,
            "hash": "a7",
            "code": "",
            "callers": ["LLMSchedulerServer.handle_request"],
            "callees": [],
            "inputs": [],
            "outputs": [],
            "parent_classes": [],
            "overrides": None,
            "overridden_by": [],
            "mro": [],
            "observations": [],
            "language": "python",
            "symbol_type": "method",
            "description": "",
            "drift": "ok",
        },
    }
    relations = {
        "edges": [
            {
                "from_id": "api/cli.py::debug_loop",
                "to_id": "api/workflow.py::run_debug_loop",
                "edge_type": "call",
                "data_in": "",
                "data_out": "",
                "outer_hash": "",
                "condition": None,
                "dispatch_key": None,
                "dispatch_value": None,
                "is_conditional": False,
            },
            {
                "from_id": "api/workflow.py::run_debug_loop",
                "to_id": "api/workflow.py::locate_bug",
                "edge_type": "call",
                "data_in": "",
                "data_out": "",
                "outer_hash": "",
                "condition": None,
                "dispatch_key": None,
                "dispatch_value": None,
                "is_conditional": False,
            },
            {
                "from_id": "api/workflow.py::run_debug_loop",
                "to_id": "api/workflow.py::verify_fix",
                "edge_type": "call",
                "data_in": "",
                "data_out": "",
                "outer_hash": "",
                "condition": None,
                "dispatch_key": None,
                "dispatch_value": None,
                "is_conditional": False,
            },
            {
                "from_id": "api/router.py::handle_request",
                "to_id": "api/workflow.py::run_debug_loop",
                "edge_type": "dispatch",
                "data_in": "",
                "data_out": "",
                "outer_hash": "",
                "condition": "method == 'debug_loop'",
                "dispatch_key": "method",
                "dispatch_value": "debug_loop",
                "is_conditional": True,
            },
            {
                "from_id": "backend/main.py::LLMSchedulerServer.handle_request",
                "to_id": "backend/main.py::LLMSchedulerServer._handle_chat_with_model",
                "edge_type": "dispatch",
                "data_in": "",
                "data_out": "",
                "outer_hash": "",
                "condition": "method == 'chat_message'",
                "dispatch_key": "method",
                "dispatch_value": "chat_message",
                "is_conditional": True,
            },
            {
                "from_id": "backend/main.py::LLMSchedulerServer.handle_request",
                "to_id": "backend/main.py::LLMSchedulerServer._handle_get_balance",
                "edge_type": "dispatch",
                "data_in": "",
                "data_out": "",
                "outer_hash": "",
                "condition": "method == 'get_balance'",
                "dispatch_key": "method",
                "dispatch_value": "get_balance",
                "is_conditional": True,
            },
        ],
        "meta": {"total_edges": 6, "by_type": {"call": 3, "dispatch": 3}, "failed": []},
    }

    with open(codedendrite / "anchors.json", "w", encoding="utf-8") as f:
        json.dump(anchors, f, ensure_ascii=False, indent=2)
    with open(codedendrite / "relations.json", "w", encoding="utf-8") as f:
        json.dump(relations, f, ensure_ascii=False, indent=2)

    api_dir = root / "api"
    api_dir.mkdir(exist_ok=True)
    (api_dir / "cli.py").write_text(
        "import argparse\n\n"
        "def debug_loop():\n    pass\n\n"
        "def main():\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('--debug-loop', action='store_true')\n"
        "    args = parser.parse_args()\n"
        "    if args.debug_loop:\n"
        "        debug_loop()\n",
        encoding="utf-8",
    )


def main() -> None:
    root = Path(__file__).resolve().parents[3] / f".tmp_module_tree_smoke_{uuid.uuid4().hex[:8]}"
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    try:
        _write_fixture(root)

        result = generate_module_tree(str(root))
        assert result["semantic_modules"], result
        assert result["call_structure_hash"], result

        module = find_module_for_symbol("api/workflow.py::run_debug_loop", str(root))
        assert module, result
        assert module["entry_functions"], module
        assert any(
            item["symbol_id"] == "api/workflow.py::run_debug_loop"
            for item in module["entry_functions"]
        ), module

        exact_module = find_module_for_symbol("api/workflow.py::run_debug_loop", str(root))
        assert exact_module, result
        assert exact_module["name"] == module["name"], exact_module

        fuzzy_module = find_module_for_symbol("run_debug_loop", str(root))
        assert fuzzy_module, result
        assert fuzzy_module["id"] == module["id"], fuzzy_module

        dispatch_module = find_module_for_symbol("LLMSchedulerServer.handle_request", str(root))
        assert dispatch_module, result
        assert any(
            "handle_request" in item.get("symbol_id", "")
            for item in dispatch_module.get("entry_functions", [])
        ), dispatch_module
        assert any(
            "_handle_chat_with_model" in item
            for item in dispatch_module.get("member_symbols", [])
        ), dispatch_module

        lookup_module = get_module(module["id"], str(root))
        assert lookup_module, module
        assert lookup_module["id"] == module["id"], lookup_module

        queried = query_modules("debug workflow", str(root))
        assert queried, result
        assert queried[0]["id"] == module["id"], queried

        out = StringIO()
        with redirect_stdout(out):
            module_query(str(root), query="debug workflow", limit=3)
        cli_output = out.getvalue()
        assert "debug_loop" in cli_output, cli_output

        out = StringIO()
        with redirect_stdout(out):
            module_query(str(root), symbol="run_debug_loop")
        cli_symbol_output = out.getvalue()
        assert "api/workflow.py::run_debug_loop" in cli_symbol_output, cli_symbol_output

        map_text = ContextBuilder(str(root)).build_map(mode="human")
        assert "## Project Modules" in map_text, map_text
        assert "run_debug_loop" in map_text, map_text

        debug_map = ContextBuilder(str(root)).build_debug_map("run_debug_loop")
        assert "## Module" in debug_map, debug_map
        assert module["name"] in debug_map, debug_map
        assert "locate_bug" in debug_map, debug_map

        summary = generate_module_summary(str(root))
        assert summary["modules"], summary
        assert "project_one_line" in summary, summary
        assert summary["reused_cache"] is False, summary

        cached = load_summary_cache(str(root))
        assert cached["call_structure_hash"] == result["call_structure_hash"], cached
        markdown = (root / ".codedendrite" / "project_summary.md").read_text(encoding="utf-8")
        assert "# " in markdown and "## Modules" in markdown, markdown

        summary2 = generate_module_summary(str(root))
        assert summary2["reused_cache"] is True, summary2

        print("PASS module_tree_smoke")
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
