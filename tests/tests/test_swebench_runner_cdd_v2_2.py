from evaluation import run_swe_cdd_v2_2 as runner


INLINE = """<think>ready</think>
<diff>
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-old
+new
diff>
"""


def test_v2_2_extracts_inline_patch_and_drops_malformed_closer():
    patch = runner._clean_inline_patch(INLINE)
    assert patch is not None
    assert patch.startswith("--- a/app.py")
    assert patch.endswith("+new")
    assert "diff>" not in patch


def test_v2_2_splits_inline_patch_without_second_model_call():
    calls = []

    def model(system, messages):
        calls.append((system, messages))
        return INLINE

    wrapped = runner.InlineDiffCallV2_2(model)
    assert wrapped("system", []) == "<diff>"
    second = wrapped("system", [{"role": "user", "content": "send patch"}])
    assert second.startswith("--- a/app.py")
    assert second.endswith("<done>")
    assert len(calls) == 1


def test_v2_2_marks_inline_diff_policy():
    meta = runner.base_meta_v2_2({}, ".")
    assert meta["nav_protocol"] == "cdd_v2_2"
    assert meta["cdd_runner_version"] == "cdd.swebench_runner.v2.2"
    assert meta["inline_diff_policy"] == "split_inline_diff_without_model_call_v2_2"
