from evaluation.analyze_anchor_paths_v4 import (
    extract_attempted_actions,
    extract_observed_nodes,
    repeated_path_stats,
)


def test_extracts_automatic_and_model_attempts_without_tool_suggestions():
    turns = [
        {"role": "user", "content": "ANCHOR a.py::A\n下一步：\n<expand> a.py::A"},
        {"role": "assistant", "turn_idx": 1, "content": "<expand> a.py::A"},
        {"role": "user", "content": "NODE a.py::A\nNEXT:\n<expand> a.py::B"},
        {"role": "assistant", "turn_idx": 2, "content": "<anchor> a.py::B\n<diff>"},
    ]
    automatic = [{"command": "anchor", "target": "a.py::A"}]
    actions = extract_attempted_actions(turns, automatic)
    assert [(item["command"], item["target"]) for item in actions] == [
        ("anchor", "a.py::A"),
        ("expand", "a.py::A"),
        ("anchor", "a.py::B"),
    ]


def test_extracts_only_successfully_observed_anchor_and_node_headers():
    turns = [
        {"role": "user", "content": "ANCHOR a.py::A\n<expand> a.py::B"},
        {"role": "assistant", "content": "<anchor> a.py::B"},
        {"role": "user", "content": "NODE a.py::B\nNEXT:\n<diff>"},
    ]
    assert extract_observed_nodes(turns) == ["a.py::A", "a.py::B"]


def test_repeated_path_counts_targets_actions_edges_and_self_loops():
    actions = [
        {"command": "anchor", "target": "A"},
        {"command": "expand", "target": "A"},
        {"command": "anchor", "target": "B"},
        {"command": "anchor", "target": "A"},
        {"command": "anchor", "target": "B"},
    ]
    stats = repeated_path_stats(actions)
    assert stats["repeated_target_count"] == 3
    assert stats["repeated_action_count"] == 2
    assert stats["repeated_edge_count"] == 1
    assert stats["self_loop_count"] == 1
    assert stats["has_repetition"] is True
