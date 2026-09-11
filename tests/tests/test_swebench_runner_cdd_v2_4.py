import subprocess

from evaluation import run_swe_cdd_v2_4 as runner


def test_v2_4_recounts_hunks_and_removes_mail_signature():
    patch = """--- a/a.py
+++ b/a.py
@@ -1,9 +1,9 @@
 a
-b
+B
 c
""" + "-- \n2.23.0\n"
    normalized, recounted, signature_removed = runner.normalize_unified_diff(patch)
    assert "@@ -1,3 +1,3 @@" in normalized
    assert normalized.endswith(" c\n")
    assert "2.23.0" not in normalized
    assert recounted == 1
    assert signature_removed is True


def test_v2_4_normalized_patch_passes_real_git_preflight(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "a.py").write_text("a\nb\nc\n", encoding="utf-8")
    malformed = """--- a/a.py
+++ b/a.py
@@ -1,8 +1,8 @@
 a
-b
+B
 c
"""
    normalized, recounted, _ = runner.normalize_unified_diff(malformed)
    applies, detail = runner.preflight_patch(str(tmp_path), normalized)
    assert recounted == 1
    assert applies is True, detail


def test_v2_4_rejects_patch_that_misses_base_context(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "a.py").write_text("different\n", encoding="utf-8")
    patch = """--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-a
+b
"""
    applies, detail = runner.preflight_patch(str(tmp_path), patch)
    assert applies is False
    assert "does not apply" in detail


def test_v2_4_marks_patch_integrity_policy():
    meta = runner.base_meta_v2_4({}, ".")
    assert meta["nav_protocol"] == "cdd_v2_4"
    assert meta["cdd_runner_version"] == "cdd.swebench_runner.v2.4"
    assert meta["patch_integrity_version"] == "cdd.patch_integrity.v2.4"
    assert meta["patch_output_policy"] == "normalize_with_advisory_preflight_v2_4"


def test_v2_4_preserves_normalized_patch_when_host_preflight_is_unverified(monkeypatch):
    malformed = """--- a/a.py
+++ b/a.py
@@ -1,8 +1,8 @@
 a
-b
+B
 c
"""
    meta = runner.base_meta_v2_4({}, ".")
    meta["resolved_repo_path"] = "/base-worktree"
    base_result = (True, True, malformed, [], None, 1, meta)
    monkeypatch.setattr(
        runner.compat_v2_3,
        "run_taskpackage_cdd_v2_3",
        lambda *args, **kwargs: base_result,
    )
    monkeypatch.setattr(
        runner,
        "preflight_patch",
        lambda repo_path, patch: (False, "host semantics differ"),
    )

    result = runner.run_taskpackage_cdd_v2_4({}, lambda *_: "", 1)

    assert result[0] is True
    assert "@@ -1,3 +1,3 @@" in result[2]
    assert result[6]["patch_preflight_status"] == "unverified"
    assert result[6]["patch_preflight_error"] == "host semantics differ"
