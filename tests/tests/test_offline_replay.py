import json
import sys
from pathlib import Path


ROOT = str(Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from evaluation.offline_replay import replay  # noqa: E402


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_partial_replay_never_extrapolates_missing_indexes(tmp_path):
    indexed = tmp_path / "indexed"
    indexed.mkdir()
    _write(indexed / ".codedendrite" / "anchors.json", {
        "pkg/fix.py::repair": {
            "id": "pkg/fix.py::repair", "symbol": "repair", "file": "pkg/fix.py",
            "line_start": 1, "line_end": 2, "hash": "fixture",
        }
    })
    tasks = [
        {
            "instance_id": "one", "repo_path": str(indexed),
            "problem_statement": "`repair` is broken in pkg/fix.py",
            "expected_files": ["pkg/fix.py"],
        },
        {
            "instance_id": "two", "repo_path": str(tmp_path / "missing"),
            "problem_statement": "unknown failure", "expected_files": ["other.py"],
        },
    ]
    tasks_path = tmp_path / "tasks.json"
    _write(tasks_path, tasks)
    run_dir = tmp_path / "run"
    _write(run_dir / "result.json", {"tasks": [
        {"task_id": "one", "idx": 0}, {"task_id": "two", "idx": 1},
    ]})
    for idx, file_name in enumerate(("wrong.py", "other.py")):
        _write(run_dir / "communication" / "swe_{}.json".format(idx), {
            "turns": [{
                "role": "user",
                "content": "SUGGESTED COMMANDS:\n<fileanchors> {}\nStart navigating.".format(file_name),
            }]
        })

    report = replay(tasks_path, run_dir)

    assert report["status"] == "partial"
    assert report["comparability"]["paired_navigation_comparison"] is False
    assert report["summary"]["tasks_total"] == 2
    assert report["summary"]["new_packet_evaluated"] == 1
    assert report["summary"]["unavailable_indexes"] == 1
    assert report["summary"]["index_statuses"]["missing_index"] == 1
    assert report["summary"]["new_packet_recall_at_1_evaluated_only"] == 1.0
    assert report["traces"][1]["new_packet"]["recall_at_1"] is None
    assert report["summary"]["ambiguous_auto_expands"] == 0
