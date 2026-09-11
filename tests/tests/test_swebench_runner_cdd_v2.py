from pathlib import Path

from evaluation import run_swe_cdd_v2 as runner


def _packet_v2():
    return {
        "version": runner.PACKET_VERSION,
        "issue": {
            "title": "handler fails",
            "char_count": 13,
            "sha256": "0" * 64,
            "raw_text_included": False,
        },
        "signals": [{
            "id": "S0",
            "kind": "exact_symbol",
            "value": "handler",
            "source": "issue",
            "strength": 2,
            "navigation_eligible": True,
        }],
        "navigation": {
            "status": "resolved",
            "confidence": "high",
            "reason": "one exact anchor",
            "candidate_files": ["app.py"],
            "strong_evidence_count": 1,
            "evidence_boundary": "static evidence only",
        },
        "candidates": [{
            "id": "C0",
            "file": "app.py",
            "anchor": "app.py::handler",
            "resolution": "exact",
            "evidence": [{"signal_id": "S0", "kind": "exact_symbol", "strength": 2}],
            "contradictions": [],
        }],
        "alternatives": [],
        "boundaries": [],
        "recommended_action": {
            "kind": "expand_anchor",
            "target": "app.py::handler",
            "argv": ["cdd", "code", "app.py::handler"],
            "because": ["S0"],
        },
        "action_policy": "one action",
    }


def test_cdd_v2_runner_versions_snapshot_and_rejects_repeat(tmp_path, monkeypatch):
    packet = _packet_v2()
    monkeypatch.setattr(
        runner.legacy,
        "ensure_codedendrite_index",
        lambda *args, **kwargs: {"anchor_count": 1, "rebuilt_index": True},
    )
    monkeypatch.setattr(
        runner,
        "create_snapshot",
        lambda *args, **kwargs: {
            "bundle": str(tmp_path / "snapshots" / "task-v2"),
            "packet": packet,
            "manifest": {"version": runner.SNAPSHOT_VERSION},
        },
    )

    tool_calls = []

    def fake_tool(cmd, arg, root, nav_meta):
        tool_calls.append((cmd, arg))
        if cmd == "expand":
            nav_meta["expanded_nodes"].append(arg)
        return "real source"

    monkeypatch.setattr(runner.legacy, "run_tool_v3", fake_tool)
    responses = iter([
        "<expand> app.py::handler",
        "<diff>",
        "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+new\n<done>",
    ])

    task = {
        "instance_id": "task-v2",
        "repo": "owner/repo",
        "repo_path": str(tmp_path),
        "_repo_resolution": "test-v2",
        "problem_statement": "handler fails",
        "expected_files": ["app.py"],
    }
    result = runner.run_taskpackage_cdd_v2(
        task,
        lambda system, messages: next(responses),
        4,
        task_cfg={
            "force_rebuild_index": True,
            "cdd_v2_snapshot_root": str(tmp_path / "snapshots"),
            "cdd_v2_max_actions": 12,
        },
    )

    success, hit, diff, _turns, error, _total_turns, meta = result
    assert success is True
    assert hit is True
    assert error is None
    assert "+++ b/app.py" in diff
    assert meta["nav_protocol"] == "cdd_v2"
    assert meta["cdd_runner_version"] == "cdd.swebench_runner.v2"
    assert meta["cdd_packet_version"] == "task_context_packet_v2"
    assert meta["cdd_snapshot_version"] == "cdd.task_snapshot.v1"
    assert meta["cdd_action_session_version"] == "cdd.action_session.v1"
    assert meta["repeated_commands_rejected"] == 1
    assert tool_calls == [("expand", "app.py::handler")]
    assert Path(meta["snapshot_bundle"]).name == "task-v2"
