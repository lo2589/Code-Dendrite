"""CDD V2.0 release gate: common languages must emit a real one-hop call chain."""

from pathlib import Path

import pytest

from analyzer.anchors import _finalize_anchor_graph
from scanner.language.pipeline import parse_paths
from analyzer.shared.types import Anchor


FIXTURES = {
    "python": ("app.py", "def helper():\n    return 1\n\ndef main():\n    return helper()\n"),
    "javascript": ("app.js", "function helper(){ return 1; }\nfunction main(){ return helper(); }\n"),
    "typescript": ("app.ts", "function helper(): number { return 1; }\nfunction main(): number { return helper(); }\n"),
    "tsx": ("app.tsx", "function helper(): number { return 1; }\nexport function main(){ return <b>{helper()}</b>; }\n"),
    "java": ("App.java", "class App { static int helper(){ return 1; } static int main(){ return helper(); } }\n"),
    "go": ("app.go", "package main\nfunc helper() int { return 1 }\nfunc main() { helper() }\n"),
    "rust": ("app.rs", "fn helper() -> i32 { 1 }\nfn main() { helper(); }\n"),
    "c": ("app.c", "int helper(){ return 1; }\nint main(){ return helper(); }\n"),
    "cpp": ("app.cpp", "int helper(){ return 1; }\nint main(){ return helper(); }\n"),
    "csharp": ("App.cs", "class App { static int helper(){ return 1; } static int main(){ return helper(); } }\n"),
    "kotlin": ("App.kt", "fun helper(): Int { return 1 }\nfun main() { helper() }\n"),
    "swift": ("App.swift", "func helper() -> Int { return 1 }\nfunc main() { helper() }\n"),
    "ruby": ("app.rb", "def helper\n  1\nend\ndef main\n  helper()\nend\n"),
    "php": ("app.php", "<?php\nfunction helper(){ return 1; }\nfunction main(){ return helper(); }\n"),
    "vue": ("App.vue", "<script setup lang=\"ts\">\nfunction helper(){ return 1 }\nfunction main(){ return helper() }\n</script>\n<template><main /></template>\n"),
    "svelte": ("App.svelte", "<script>\nfunction helper(){ return 1 }\nfunction main(){ return helper() }\n</script>\n<button on:click={main}>run</button>\n"),
}


def _anchors(parsed):
    anchors = {
        item.id: Anchor(
            id=item.id,
            symbol=item.symbol,
            file=item.file,
            line_start=item.line_start,
            line_end=item.line_end,
            hash=item.hash,
            language=item.language,
            symbol_type=item.symbol_type,
            parent_anchor=item.parent_anchor,
            callees=item.callees,
            call_sites=item.call_sites,
        )
        for item in parsed.values()
    }
    _finalize_anchor_graph(anchors)
    return anchors


def _named(anchors, name):
    values = [anchor for anchor in anchors.values() if anchor.symbol.rsplit(".", 1)[-1] == name]
    assert len(values) == 1, [(item.id, item.symbol) for item in values]
    return values[0]


@pytest.mark.parametrize("language", FIXTURES)
def test_common_language_main_calls_helper(language: str, tmp_path: Path):
    filename, source = FIXTURES[language]
    path = tmp_path / filename
    path.write_text(source, encoding="utf-8")

    parsed, failures, completed = parse_paths(tmp_path, [path], include_python=True)
    assert not failures
    assert filename in completed
    anchors = _anchors(parsed)
    main = _named(anchors, "main")
    helper = _named(anchors, "helper")

    assert helper.id in main.callees, (language, main.id, main.call_sites)
    assert main.id in helper.callers, (language, helper.id, helper.callers)


def test_mixed_typescript_to_python_http_chain(tmp_path: Path):
    client = tmp_path / "client.ts"
    server = tmp_path / "server.py"
    client.write_text("export async function main(){ return fetch('/health'); }\n", encoding="utf-8")
    server.write_text("@app.get('/health')\ndef health():\n    return {'ok': True}\n", encoding="utf-8")

    from analyzer.anchors import generate_all_anchors, load_anchors

    generate_all_anchors(str(tmp_path))
    anchors = load_anchors(str(tmp_path))
    main = anchors["client.ts::main"]
    health = anchors["server.py::health"]
    bridge = [site for site in main.call_sites if site.get("bridge_kind") == "http"]

    assert health.id in main.callees
    assert bridge and bridge[0]["evidence"] == "literal-http-method-path"
