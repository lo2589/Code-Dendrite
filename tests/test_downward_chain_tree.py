import json

from tools.CodeDendrite.api.inspector import get_downward_chain, get_upward_chain


def _anchor(anchor_id, symbol, callees):
    return {
        "id": anchor_id,
        "symbol": symbol,
        "file": anchor_id.split("::", 1)[0],
        "line_start": 1,
        "line_end": 2,
        "hash": "test",
        "callees": callees,
    }


def test_downward_chain_keeps_same_node_under_each_parent(tmp_path):
    index_dir = tmp_path / ".codedendrite"
    index_dir.mkdir()
    anchors = {
        "app.py::root": _anchor("app.py::root", "root", ["app.py::left", "app.py::shared"]),
        "app.py::left": _anchor("app.py::left", "left", ["app.py::shared"]),
        "app.py::shared": _anchor("app.py::shared", "shared", []),
    }
    (index_dir / "anchors.json").write_text(json.dumps(anchors), encoding="utf-8")

    chain = get_downward_chain("app.py::root", str(tmp_path), max_depth=4)

    assert [(item["id"], item["depth"], item["parent_id"]) for item in chain] == [
        ("app.py::root", 0, None),
        ("app.py::left", 1, "app.py::root"),
        ("app.py::shared", 2, "app.py::left"),
        ("app.py::shared", 1, "app.py::root"),
    ]


def test_downward_chain_stops_cycles_only_on_current_path(tmp_path):
    index_dir = tmp_path / ".codedendrite"
    index_dir.mkdir()
    anchors = {
        "app.py::root": _anchor("app.py::root", "root", ["app.py::child"]),
        "app.py::child": _anchor("app.py::child", "child", ["app.py::root"]),
    }
    (index_dir / "anchors.json").write_text(json.dumps(anchors), encoding="utf-8")

    chain = get_downward_chain("app.py::root", str(tmp_path), max_depth=10)

    assert [item["id"] for item in chain] == ["app.py::root", "app.py::child"]


def test_upward_chain_keeps_shared_entry_under_each_caller(tmp_path):
    index_dir = tmp_path / ".codedendrite"
    index_dir.mkdir()
    anchors = {
        "app.py::root": _anchor("app.py::root", "root", []),
        "app.py::left": _anchor("app.py::left", "left", []),
        "app.py::shared": _anchor("app.py::shared", "shared", []),
    }
    (index_dir / "anchors.json").write_text(json.dumps(anchors), encoding="utf-8")
    (index_dir / "relations.json").write_text(json.dumps({"edges": [
        {"from_id": "app.py::root", "to_id": "app.py::shared", "edge_type": "call"},
        {"from_id": "app.py::left", "to_id": "app.py::shared", "edge_type": "call"},
        {"from_id": "app.py::root", "to_id": "app.py::left", "edge_type": "call"},
    ]}), encoding="utf-8")

    chain = get_upward_chain("app.py::shared", str(tmp_path), max_depth=4)

    assert [(item["id"], item["depth"], item["parent_id"]) for item in chain] == [
        ("app.py::shared", 0, None),
        ("app.py::root", 1, "app.py::shared"),
        ("app.py::left", 1, "app.py::shared"),
        ("app.py::root", 2, "app.py::left"),
    ]


def test_yaml_active_keys_filter_registry_template_branches(tmp_path):
    index_dir = tmp_path / ".codedendrite"
    index_dir.mkdir()
    root = _anchor(
        "app.py::root",
        "root",
        ["app.py::real_user", "app.py::json_input"],
    )
    root["call_sites"] = [
        {
            "target": "app.py::real_user",
            "registry_template": "input.type.*",
            "registry_key": "input.type.real_user",
        },
        {
            "target": "app.py::json_input",
            "registry_template": "input.type.*",
            "registry_key": "input.type.json",
        },
    ]
    anchors = {
        "app.py::root": root,
        "app.py::real_user": _anchor("app.py::real_user", "real_user", []),
        "app.py::json_input": _anchor("app.py::json_input", "json_input", []),
    }
    (index_dir / "anchors.json").write_text(json.dumps(anchors), encoding="utf-8")

    chain = get_downward_chain(
        "app.py::root",
        str(tmp_path),
        max_depth=2,
        active_registry_keys={"input.type.real_user"},
    )

    assert [item["id"] for item in chain] == ["app.py::root", "app.py::real_user"]
    assert chain[1]["yaml_selected"] is True
    assert chain[1]["registry_key"] == "input.type.real_user"
    assert chain[1]["registry_template"] == "input.type.*"


def test_yaml_factory_expands_only_keys_selected_for_that_call(tmp_path):
    index_dir = tmp_path / ".codedendrite"
    index_dir.mkdir()
    root = _anchor("app.py::root", "root", ["registry.py::create"])
    root["call_sites"] = [{
        "target": "registry.py::create",
        "factory_config_paths": ["architecture"],
    }]
    wanted = _anchor("models.py::Wanted", "Wanted", [])
    wanted["symbol_type"] = "class"
    wanted["registered_as"] = "Wanted"
    other = _anchor("models.py::Other", "Other", [])
    other["symbol_type"] = "class"
    other["registered_as"] = "Other"
    anchors = {
        "app.py::root": root,
        "registry.py::create": _anchor("registry.py::create", "create", []),
        "models.py::Wanted": wanted,
        "models.py::Other": other,
    }
    (index_dir / "anchors.json").write_text(json.dumps(anchors), encoding="utf-8")

    chain = get_downward_chain(
        "app.py::root",
        str(tmp_path),
        max_depth=3,
        active_registry_keys={"Wanted", "Other"},
        yaml_profile={"flat": {"architecture": "Wanted"}},
    )

    assert [item["id"] for item in chain] == [
        "app.py::root",
        "registry.py::create",
        "models.py::Wanted",
    ]
    assert chain[2]["yaml_selected"] is True
