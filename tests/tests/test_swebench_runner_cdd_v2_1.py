from evaluation import run_swe_cdd_v2_1 as runner


def test_v2_1_keeps_only_first_command():
    commands = runner.extract_first_command_v2_1(
        "<grep> method_decorator tests/test_decorators.py\n<diff>"
    )
    assert [(cmd, arg) for cmd, arg, _start, _end in commands] == [
        ("grep", "method_decorator tests/test_decorators.py")
    ]


def test_v2_1_marks_its_policy_and_navigation_limit():
    meta = runner.base_meta_v2_1({}, ".")
    assert meta["nav_protocol"] == "cdd_v2_1"
    assert meta["cdd_runner_version"] == "cdd.swebench_runner.v2.1"
    assert meta["multi_command_policy"] == "first_command_only_v2_1"
    assert meta["navigation_action_limit"] == 6


def test_v2_1_tool_forces_diff_after_navigation_limit(monkeypatch):
    monkeypatch.setattr(runner, "_ORIGINAL_RUN_TOOL", lambda *args: "TOOL RESULT")
    result = runner.run_tool_with_budget_v2_1(
        "read", "app.py:1-20", ".", {"valid_commands": 6},
    )
    assert "navigation limit reached" in result
    assert result.endswith("NEXT:\n<diff>")
