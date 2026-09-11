import json
import subprocess
import sys
from pathlib import Path


ROOT = str(Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from synth.api.action_session import apply_action_gate, record_action  # noqa: E402
from synth.api.issue_evidence_packet import (  # noqa: E402
    generate_issue_evidence_packet,
    validate_issue_evidence_packet,
)
from evaluation.offline_replay import replay  # noqa: E402
from evaluation.snapshot import create_snapshot, verify_snapshot  # noqa: E402


def _git_repo(path):
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True)
    (path / "app.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "app.py"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "fixture"], check=True)
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def _anchors(root):
    target = root / ".codedendrite" / "anchors.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({
        "app.py::handler": {
            "id": "app.py::handler", "symbol": "handler", "file": "app.py",
            "line_start": 1, "line_end": 2, "hash": "fixture",
        }
    }), encoding="utf-8")


def test_snapshot_is_commit_bound_and_hash_verified(tmp_path):
    repo = tmp_path / "repo"
    commit = _git_repo(repo)
    _anchors(repo)
    result = create_snapshot(
        repo, "`handler` in app.py fails", tmp_path / "snapshots",
        instance_id="task-one", expected_commit=commit,
    )
    bundle = Path(result["bundle"])
    assert verify_snapshot(bundle, expected_commit=commit) == (True, "verified")
    assert result["manifest"]["tracked_source_dirty"] is False

    anchors = bundle / ".codedendrite" / "anchors.json"
    anchors.write_text(anchors.read_text() + "\n", encoding="utf-8")
    assert verify_snapshot(bundle, expected_commit=commit) == (False, "hash_mismatch")


def test_replay_rejects_stale_working_tree_index(tmp_path):
    repo = tmp_path / "repo"
    commit = _git_repo(repo)
    _anchors(repo)
    tasks = [{
        "instance_id": "task-one", "repo_path": str(repo),
        "base_commit": "0" * 40, "problem_statement": "`handler` fails",
        "expected_files": ["app.py"],
    }]
    tasks_path = tmp_path / "tasks.json"
    tasks_path.write_text(json.dumps(tasks), encoding="utf-8")
    run = tmp_path / "run"
    (run / "communication").mkdir(parents=True)
    (run / "result.json").write_text(json.dumps({"tasks": [{"task_id": "task-one", "idx": 0}]}))
    (run / "communication" / "swe_0.json").write_text(json.dumps({"turns": []}))

    report = replay(tasks_path, run)
    assert commit != tasks[0]["base_commit"]
    assert report["summary"]["new_packet_evaluated"] == 0
    assert report["summary"]["index_statuses"] == {"stale_commit": 1}
    assert report["traces"][0]["new_packet"]["recall_at_1"] is None


def test_action_session_stops_a_repeated_action(tmp_path):
    anchors = {
        "app.py::handler": {
            "id": "app.py::handler", "symbol": "handler", "file": "app.py",
            "line_start": 1, "line_end": 2,
        }
    }
    packet = generate_issue_evidence_packet("`handler` in app.py fails", anchors=anchors)
    first = apply_action_gate(packet, tmp_path, "task-one")
    assert first["execution"]["status"] == "ready"

    action = first["recommended_action"]
    recorded = record_action(tmp_path, "task-one", action["kind"], action["target"])
    assert recorded["recorded"] is True
    assert record_action(tmp_path, "task-one", action["kind"], action["target"])["repeated"] is True

    second = apply_action_gate(packet, tmp_path, "task-one")
    assert second["recommended_action"] is None
    assert second["execution"]["status"] == "stopped"
    assert second["execution"]["stop_reason"] == "repeated_action"
    validate_issue_evidence_packet(second)
