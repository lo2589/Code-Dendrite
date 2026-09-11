from evaluation import run_swe_cdd_v2_3 as runner


def test_v2_3_converts_seventh_navigation_reply_to_diff():
    calls = []

    def model(system, messages):
        calls.append(1)
        return "<read> app.py:1-20"

    wrapped = runner.BoundedProtocolCallV2_3(model)
    for _ in range(6):
        assert wrapped("system", []) == "<read> app.py:1-20"
    assert wrapped("system", []) == "<diff>"
    assert len(calls) == 7


def test_v2_3_preserves_inline_patch_policy():
    calls = []

    def model(system, messages):
        calls.append(1)
        return "<diff>\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-a\n+b\n<done>"

    wrapped = runner.BoundedProtocolCallV2_3(model)
    assert wrapped("system", []) == "<diff>"
    assert wrapped("system", []) == "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-a\n+b\n<done>"
    assert len(calls) == 1


def test_v2_3_marks_hard_navigation_policy():
    meta = runner.base_meta_v2_3({}, ".")
    assert meta["nav_protocol"] == "cdd_v2_3"
    assert meta["cdd_runner_version"] == "cdd.swebench_runner.v2.3"
    assert meta["navigation_action_limit"] == 6
    assert meta["navigation_limit_policy"] == "seventh_navigation_becomes_diff_v2_3"
