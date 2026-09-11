from pathlib import Path

import pytest

from index.api.anchors import (
    _finalize_anchor_graph,
    generate_all_anchors,
    load_anchors,
    update_anchors_for_files,
)
from parse.languages.pipeline import parse_paths
from parse.languages.registry import language_for_path


def _write(path: Path, source: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def test_registry_covers_common_and_mixed_language_extensions():
    expected = {
        ".py": "python", ".ts": "typescript", ".js": "javascript",
        ".c": "cpp", ".cpp": "cpp", ".java": "java", ".kt": "kotlin",
        ".go": "go", ".rs": "rust", ".swift": "swift", ".php": "php",
        ".rb": "ruby", ".cs": "csharp", ".scala": "scala",
        ".m": "objective-c", ".sh": "shell", ".ps1": "powershell",
        ".vue": "vue", ".svelte": "svelte", ".sql": "sql",
        ".yaml": "yaml", ".json": "json", ".toml": "toml",
    }
    assert {ext: language_for_path("x" + ext).name for ext in expected} == expected


def test_language_pipeline_emits_callable_anchors_and_exact_unique_edges(tmp_path):
    files = [
        _write(tmp_path / "web.ts", "function main(){ helper(); }\nfunction helper(){}\n"),
        _write(tmp_path / "worker.go", "package main\nfunc Start(){ Stop() }\nfunc Stop(){}\n"),
        _write(tmp_path / "Worker.java", "class Worker { void run(){ done(); } void done(){} }\n"),
        _write(tmp_path / "Program.cs", "class Program { public void Main(){ Run(); } public void Run(){} }\n"),
        _write(tmp_path / "task.sh", "start() { finish; finish; }\nfinish() { true; }\n"),
        _write(tmp_path / "App.vue", "<script>function boot(){ ready(); } function ready(){}</script>\n"),
    ]
    parsed, failures, completed = parse_paths(tmp_path, files)
    assert not failures
    assert completed == {path.name for path in files}

    from base.shared.types import Anchor
    anchors = {
        item.id: Anchor(
            id=item.id, symbol=item.symbol, file=item.file,
            line_start=item.line_start, line_end=item.line_end, hash=item.hash,
            language=item.language, symbol_type=item.symbol_type,
            parent_anchor=item.parent_anchor, callees=item.callees,
            call_sites=item.call_sites,
        )
        for item in parsed.values()
    }
    _finalize_anchor_graph(anchors)
    assert anchors["web.ts::main"].callees == ["web.ts::helper"]
    assert anchors["worker.go::Start"].callees == ["worker.go::Stop"]
    assert anchors["Program.cs::Program.Main"].callees == ["Program.cs::Program.Run"]
    assert anchors["task.sh::start"].callees == ["task.sh::finish"]
    assert anchors["App.vue::boot"].callees == ["App.vue::ready"]


def test_typescript_incremental_update_matches_full_language_path(tmp_path):
    source = _write(tmp_path / "app.ts", "function main(){ first(); }\nfunction first(){}\n")
    generate_all_anchors(str(tmp_path))
    anchors = load_anchors(str(tmp_path))
    assert anchors["app.ts::main"].callees == ["app.ts::first"]

    source.write_text("function main(){ second(); }\nfunction second(){}\n", encoding="utf-8")
    result = update_anchors_for_files(str(tmp_path), [source])
    assert result["failed"] == 0
    anchors = load_anchors(str(tmp_path))
    assert "app.ts::first" not in anchors
    assert anchors["app.ts::main"].callees == ["app.ts::second"]


def test_non_python_control_flow_overlay(tmp_path):
    source = _write(
        tmp_path / "app.ts",
        "function main(flag){ if(flag){ work(); } else { stop(); } }\n"
        "function work(){}\nfunction stop(){}\n",
    )
    from serve.api.control_flow_dispatch import extract_file_control_flow
    virtual = extract_file_control_flow(tmp_path, source.name, source.read_text())
    blocks = list(virtual.values())
    assert blocks
    assert blocks[0].parent_anchor == "app.ts::main"
    assert blocks[0].virtual_kind == "condition"
    assert any(site["target"] == "work" for site in blocks[0].call_sites)


def test_literal_http_bridge_connects_typescript_client_to_python_route(tmp_path):
    _write(
        tmp_path / "api.py",
        "from flask import Flask\napp = Flask(__name__)\n"
        "@app.post('/v1/items')\ndef save():\n    return {}\n",
    )
    _write(
        tmp_path / "web.ts",
        "export async function submit(){\n"
        "  return fetch('/v1/items', {method: 'POST'});\n}\n",
    )
    generate_all_anchors(str(tmp_path))
    anchors = load_anchors(str(tmp_path))
    submit = anchors["web.ts::submit"]
    assert "api.py::save" in submit.callees
    site = next(site for site in submit.call_sites if site.get("target") == "api.py::save")
    assert site["bridge_kind"] == "http"
    assert site["resolution"] == "exact"


@pytest.mark.parametrize(("filename", "source", "anchor_id"), [
    ("main.cpp", "void helper(){} void main(){ helper(); }", "main.cpp::main"),
    ("Worker.java", "class Worker { void run(){} }", "Worker.java::Worker.run"),
    ("Main.kt", "class Main { fun run() { done() } fun done(){} }", "Main.kt::Main.run"),
    ("main.rs", "fn run(){ done(); } fn done(){}", "main.rs::run"),
    ("Main.swift", "class Main { func run() { done() } func done(){} }", "Main.swift::Main.run"),
    ("main.php", "<?php function run(){ done(); } function done(){}", "main.php::run"),
    ("main.rb", "def run\n done()\nend\ndef done\nend\n", "main.rb::run"),
    ("Main.scala", "object Main { def run() { done() }; def done() {} }", "Main.scala::Main.run"),
    ("Main.m", "@implementation Main\n- (void)run { [self done]; }\n@end", "Main.m::Main.run"),
    ("main.ps1", "function Start-Job { Invoke-Work() }", "main.ps1::Start-Job"),
    ("main.sql", "CREATE PROCEDURE run AS BEGIN SELECT 1; END;", "main.sql::run"),
    ("App.svelte", "<script>function run(){ done(); } function done(){}</script>", "App.svelte::run"),
])
def test_each_supported_language_emits_callable_anchor(tmp_path, filename, source, anchor_id):
    path = _write(tmp_path / filename, source)
    parsed, failures, _completed = parse_paths(tmp_path, [path])
    assert not failures
    assert anchor_id in parsed
