from rl_trace.line_anchor import anchor_for_line
from rl_trace.label import _contributing_blame, _label_steps
from rl_trace.normalize import normalize_steps, parse_commands
from rl_trace.schema import StepRecord


def test_parse_commands_keeps_every_command_for_protocol_labeling():
    commands = parse_commands("<anchor> a.py::A\n<diff>")
    assert commands == [
        {"command": "anchor", "argument": "a.py::A"},
        {"command": "diff", "argument": ""},
    ]


def test_normalizer_separates_attempted_and_executed_multi_command():
    turns = [
        {"turn_idx": 1, "role": "assistant", "content": "<anchor> a.py::A\n<diff>"},
        {"turn_idx": 2, "role": "user", "content": "无效操作：只输出一条命令。"},
    ]
    step = normalize_steps(turns)[0]
    assert step.attempted_action == {"command": "anchor", "argument": "a.py::A"}
    assert step.accepted is False
    assert step.executed_action is None
    assert step.rejection_reason == "multiple_commands"


def test_normalizer_detects_runner_target_conflation():
    turns = [
        {"turn_idx": 1, "role": "assistant", "content": "<expand> a.py::A"},
        {"turn_idx": 2, "role": "user", "content": "CDD V2.6 拒绝重复操作。"},
    ]
    automatic = [{"command": "anchor", "target": "a.py::A"}]
    steps = normalize_steps(turns, automatic)
    assert steps[1].rejection_reason == "runner_target_conflation"


def test_line_to_anchor_prefers_smallest_enclosing_anchor():
    anchors = {
        "a.py::C": {
            "file": "a.py",
            "line_start": 1,
            "line_end": 20,
            "symbol_type": "class",
        },
        "a.py::C.f": {
            "file": "a.py",
            "line_start": 5,
            "line_end": 8,
            "symbol_type": "method",
        },
    }
    mapped = anchor_for_line(anchors, "a.py", 6)
    assert mapped["anchor"] == "a.py::C.f"
    assert mapped["confidence"] == "exact"


def test_accepted_retry_after_rejected_attempt_is_not_labeled_loop():
    rejected = StepRecord(
        step_idx=0,
        turn_idx=1,
        source="model",
        action_raw="<anchor> a.py::B\n<diff>",
        attempted_action={"command": "anchor", "argument": "a.py::B"},
        accepted=False,
        rejection_reason="multiple_commands",
    )
    retried = StepRecord(
        step_idx=1,
        turn_idx=3,
        source="model",
        action_raw="<anchor> a.py::B",
        attempted_action={"command": "anchor", "argument": "a.py::B"},
        accepted=True,
        executed_action={"command": "anchor", "argument": "a.py::B"},
        observed_anchors=["a.py::B"],
    )
    graph = {"a.py::A": {"a.py::B"}, "a.py::B": {"a.py::A"}}
    _label_steps(
        [rejected, retried],
        "a.py::A",
        ["a.py::B"],
        graph,
        graph,
        max_hops=4,
    )
    assert retried.process_label == "REACHED_GOLDEN"


def test_terminal_keeps_independent_contributing_blame():
    steps = [
        StepRecord(
            step_idx=0,
            turn_idx=1,
            source="model",
            action_raw="<expand> a.py::A",
            responsibility="RUNNER_PROTOCOL_ERROR",
        ),
        StepRecord(
            step_idx=1,
            turn_idx=3,
            source="model",
            action_raw="<expand> a.py::B\n<diff>",
            responsibility="MODEL_PROTOCOL_ERROR",
        ),
    ]
    labels = _contributing_blame(
        "INFRA_LLM_ERROR",
        {"error": "llm_error: closed"},
        {"path_a_to_b": {"path": ["a.py::A", "a.py::B"]}, "patch_present": False},
        steps,
    )
    assert labels == ["RUNNER_PROTOCOL_ERROR", "MODEL_PROTOCOL_ERROR"]
