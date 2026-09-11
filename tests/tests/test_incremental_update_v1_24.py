from pathlib import Path

from serve.api import cli
import tools.CodeDendrite as codedendrite_api
from tools.CodeDendrite.api import anchors as anchor_api
from tools.CodeDendrite.hash import database


def test_explicit_changed_files_refresh_only_requested_topology(monkeypatch, tmp_path: Path):
    codedendrite = tmp_path / ".codedendrite"
    codedendrite.mkdir()
    (codedendrite / "anchors.json").write_text("{}", encoding="utf-8")
    (codedendrite / "relations.json").write_text("{}", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "one.py").write_text("def one():\n    return 1\n", encoding="utf-8")
    (tmp_path / "src" / "two.py").write_text("def two():\n    return 2\n", encoding="utf-8")

    calls = {"tree": 0, "summary": 0}

    class FakeDatabase:
        def __init__(self, root):
            calls["db_root"] = root

        def update(self, files):
            calls["hash_files"] = sorted(files)
            return len(files)

    def changed(*, changed_files, root, include_virtual_blocks):
        calls["changed_files"] = changed_files
        calls["changed_root"] = root
        calls["virtual"] = include_virtual_blocks
        return {"anchors.updated": len(changed_files)}

    def tree(*, root):
        calls["tree"] += 1
        return {"semantic_modules": []}

    def summary(*, root):
        calls["summary"] += 1
        return {"modules": []}

    monkeypatch.setattr(database, "HashDatabase", FakeDatabase)
    monkeypatch.setattr(codedendrite_api, "on_files_changed", changed)
    monkeypatch.setattr(codedendrite_api, "generate_relations", lambda *, root: {"total": 0, "by_type": {}})
    monkeypatch.setattr(codedendrite_api, "generate_module_tree", tree)
    monkeypatch.setattr(codedendrite_api, "generate_module_summary", summary)
    monkeypatch.setattr(anchor_api, "load_anchors", lambda root: {})

    cli.update(
        str(tmp_path),
        changed_files=["src/one.py", str(tmp_path / "src" / "two.py"), "src/one.py"],
        topology_only=True,
    )

    assert calls["changed_files"] == ["src/one.py", "src/two.py"]
    assert calls["hash_files"] == ["src/one.py", "src/two.py"]
    assert calls["tree"] == 0
    assert calls["summary"] == 0


def test_explicit_changed_file_cannot_escape_project(tmp_path: Path):
    codedendrite = tmp_path / ".codedendrite"
    codedendrite.mkdir()
    (codedendrite / "anchors.json").write_text("{}", encoding="utf-8")
    (codedendrite / "relations.json").write_text("{}", encoding="utf-8")

    outside = tmp_path.parent / "outside.py"
    try:
        cli.update(str(tmp_path), changed_files=[str(outside)], topology_only=True)
    except SystemExit as exc:
        assert "escapes project root" in str(exc)
    else:
        raise AssertionError("outside changed file should be rejected")
