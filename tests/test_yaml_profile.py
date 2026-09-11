from serve.api.yaml_profile import (
    active_registered_keys,
    load_yaml_profile,
    yaml_component_graph,
)
from base.shared.types import Anchor


def test_yaml_profile_uses_project_loader(tmp_path):
    loader_file = tmp_path / "project_loader.py"
    loader_file.write_text(
        "def load_config(path):\n"
        "    return {'route': 'project_parsed', 'source_name': path.name}\n",
        encoding="utf-8",
    )
    yaml_file = tmp_path / "route.yaml"
    yaml_file.write_text("route: raw_yaml\n", encoding="utf-8")
    loader = Anchor(
        id="project_loader.py::load_config",
        symbol="load_config",
        file="project_loader.py",
        line_start=1,
        line_end=2,
        hash="test",
        registered_as="config.load",
    )

    profile = load_yaml_profile(yaml_file, tmp_path, {loader.id: loader})

    assert profile["loader"] == loader.id
    assert profile["data"] == {
        "route": "project_parsed",
        "source_name": "route.yaml",
    }
    assert "project_parsed" in profile["tokens"]


def test_active_keys_use_yaml_field_path_not_global_value_collision():
    def registered(anchor_id, key):
        return Anchor(
            id=anchor_id,
            symbol=anchor_id,
            file="routes.py",
            line_start=1,
            line_end=2,
            hash="test",
            registered_as=key,
        )

    anchors = {
        "print.none": registered("print.none", "print.none"),
        "print.tables": registered("print.tables", "print.tables"),
        "tools.none": registered("tools.none", "tools.none"),
        "input.real": registered("input.real", "input.type.real_user"),
    }
    profile = {
        "flat": {
            "runtime.print.type": "tables",
            "chat.tools": "none",
            "input_data.type": "real_user",
        }
    }

    assert active_registered_keys(anchors, profile) == {
        "print.tables",
        "tools.none",
        "input.type.real_user",
    }


def test_yaml_profile_falls_back_safely_when_project_has_no_loader(tmp_path):
    yaml_file = tmp_path / "model.yaml"
    yaml_file.write_text("backbone:\n  - [-1, 1, Conv, [64, 3, 2]]\n", encoding="utf-8")

    profile = load_yaml_profile(yaml_file, tmp_path, {})

    assert profile["loader"] == "PyYAML.safe_load (fallback)"
    assert profile["data"]["backbone"][0][2] == "Conv"


def test_yaml_fallback_merges_recursive_base_files_and_activates_mapping_keys(tmp_path):
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    (base_dir / "model.yml").write_text(
        "architecture: YOLOv3\n"
        "CSPResNet:\n"
        "  layers: [3, 6, 6, 3]\n",
        encoding="utf-8",
    )
    root_yaml = tmp_path / "train.yml"
    root_yaml.write_text(
        "_BASE_: [base/model.yml]\n"
        "CSPResNet:\n"
        "  width_mult: 0.5\n",
        encoding="utf-8",
    )
    architecture = Anchor(
        id="models.py::YOLOv3",
        symbol="YOLOv3",
        file="models.py",
        line_start=1,
        line_end=2,
        hash="test",
        symbol_type="class",
        registered_as="YOLOv3",
        block_metadata={"decorators": [{
            "name": "register", "key": "YOLOv3", "implicit_key": True,
        }]},
    )
    backbone = Anchor(
        id="models.py::CSPResNet",
        symbol="CSPResNet",
        file="models.py",
        line_start=3,
        line_end=4,
        hash="test",
        symbol_type="class",
        registered_as="CSPResNet",
        block_metadata={"decorators": [{
            "name": "register", "key": "CSPResNet", "implicit_key": True,
        }]},
    )
    anchors = {architecture.id: architecture, backbone.id: backbone}

    profile = load_yaml_profile(root_yaml, tmp_path, anchors)

    assert profile["loader"] == "PyYAML.safe_load+_BASE_ (fallback)"
    assert profile["data"]["architecture"] == "YOLOv3"
    assert profile["data"]["CSPResNet"] == {
        "layers": [3, 6, 6, 3],
        "width_mult": 0.5,
    }
    assert active_registered_keys(anchors, profile) == {"YOLOv3", "CSPResNet"}


def test_yaml_component_graph_requires_unique_exact_class_anchor():
    conv = Anchor(
        id="layers.py::Conv",
        symbol="Conv",
        file="layers.py",
        line_start=1,
        line_end=2,
        hash="test",
        symbol_type="class",
    )
    profile = {
        "data": {
            "backbone": [[-1, 1, "Conv", [64, 3, 2]]],
            "head": [[[-1, 0], 1, "External", []]],
        }
    }

    graph = yaml_component_graph({conv.id: conv}, profile)

    assert graph == [
        {
            "index": 0,
            "path": "backbone.0",
            "from": -1,
            "repeats": 1,
            "component": "Conv",
            "anchor_id": "layers.py::Conv",
            "resolution": "exact",
        },
        {
            "index": 1,
            "path": "head.0",
            "from": [-1, 0],
            "repeats": 1,
            "component": "External",
            "anchor_id": None,
            "resolution": "unresolved",
        },
    ]
