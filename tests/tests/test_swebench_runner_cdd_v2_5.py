from evaluation import run_swe_cdd_v2_5 as runner


def test_v2_5_marks_soft_prior_and_repair_policy():
    meta = runner.base_meta_v2_5({}, ".")
    assert meta["nav_protocol"] == "cdd_v2_5"
    assert meta["cdd_runner_version"] == "cdd.swebench_runner.v2.5"
    assert meta["soft_prior_policy"] == "anchor_graph_priority_not_boundary_v2_5"
    assert meta["patch_repair_limit"] == 1


def test_v2_5_soft_wrapper_reserves_diff_after_seven_navigation_replies():
    responses = iter(["<read> a.py:1-2</read>"] * 8)
    wrapped = runner.SoftPriorProtocolCallV2_5(lambda *_: next(responses))
    for _ in range(7):
        assert wrapped("", []) == "<read> a.py:1-2</read>"
    assert wrapped("", []) == "<diff>"


def test_v2_5_extracts_fenced_repair_patch():
    response = """```diff
--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-old
+new
```
<done>"""
    patch = runner.extract_unified_diff(response)
    assert patch is not None
    assert patch.startswith("--- a/a.py")
    assert "```" not in patch


def test_v2_5_replaces_unverified_patch_only_after_accepted_repair(monkeypatch):
    original = """--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-missing
+bad
"""
    repaired = """--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-old
+new
"""
    meta = runner.base_meta_v2_5({}, ".")
    meta["resolved_repo_path"] = "/base"
    base_result = (True, True, original, [], None, 1, meta)
    monkeypatch.setattr(runner, "_ORIGINAL_RUN_TASKPACKAGE", lambda *a, **k: base_result)
    monkeypatch.setattr(
        runner.compat_v2_4,
        "preflight_patch",
        lambda _repo, patch: (("-old" in patch), "accepted" if "-old" in patch else "missing context"),
    )
    monkeypatch.setattr(runner, "repair_patch_once", lambda *a, **k: (repaired, ""))

    result = runner.run_taskpackage_cdd_v2_5({}, lambda *_: "", 1)

    assert "-old" in result[2]
    assert result[6]["patch_preflight_status"] == "accepted_after_repair"
    assert result[6]["patch_repair_status"] == "accepted"


def test_v2_5_preserves_original_when_repair_is_rejected(monkeypatch):
    original = """--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-missing
+bad
"""
    meta = runner.base_meta_v2_5({}, ".")
    meta["resolved_repo_path"] = "/base"
    base_result = (True, True, original, [], None, 1, meta)
    monkeypatch.setattr(runner, "_ORIGINAL_RUN_TASKPACKAGE", lambda *a, **k: base_result)
    monkeypatch.setattr(runner.compat_v2_4, "preflight_patch", lambda *_: (False, "still bad"))
    monkeypatch.setattr(runner, "repair_patch_once", lambda *a, **k: (original, ""))

    result = runner.run_taskpackage_cdd_v2_5({}, lambda *_: "", 1)

    assert "-missing" in result[2]
    assert result[6]["patch_repair_status"] == "rejected"
