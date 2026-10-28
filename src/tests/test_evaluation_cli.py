"""Exercise the public snapshot → replay → validate → summary journey."""

import json
import subprocess
import sys
from pathlib import Path


CLI = Path(__file__).resolve().parents[1] / "usage" / "cli" / "cdd"


def _run(*args, cwd=None, expected=0):
    proc = subprocess.run([sys.executable, str(CLI), *map(str, args)],
                          cwd=cwd, text=True, capture_output=True, timeout=90)
    assert proc.returncode == expected, proc.stdout + proc.stderr
    return proc.stdout + proc.stderr


def test_evaluation_cli_end_to_end(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pricing.py").write_text(
        "def discount(total):\n    return total * 0.8\n", encoding="utf-8")
    issue = project / "issue.md"
    issue.write_text("Fix pricing.py discount when total is negative.\n", encoding="utf-8")
    for args in (("init",), ("config", "user.name", "CDD Test"),
                 ("config", "user.email", "test@example.invalid"),
                 ("add", "."), ("commit", "-m", "fixture")):
        subprocess.run(["git", *args], cwd=project, check=True, capture_output=True)

    snapshots = tmp_path / "snapshots"
    run_dir = tmp_path / "run"
    tasks = tmp_path / "tasks.json"
    tasks.write_text(json.dumps({"tasks": [{
        "instance_id": "pricing-1", "expected_files": ["pricing.py"],
        "official_resolved": False,
    }]}), encoding="utf-8")

    _run("snapshot", issue, snapshots, project, "--instance-id", "pricing-1")
    manifest = json.loads((snapshots / "pricing-1" / "manifest.json").read_text())
    assert manifest["index_sha256"]["anchors.json"]
    _run("replay", tasks, run_dir, "--snapshot-dir", snapshots)
    report = run_dir / "replay-report.json"
    _run("eval", "validate", report)
    summary = _run("eval", "summary", report)
    assert '"total": 1' in summary
    assert json.loads(report.read_text())["summary"]["localization"]["current_hit"] == 1

    data = json.loads(report.read_text())
    data["summary"]["total"] = 99
    report.write_text(json.dumps(data), encoding="utf-8")
    _run("eval", "validate", report, expected=1)

    index_file = snapshots / "pricing-1" / "index" / "anchors.json"
    index_file.write_text("{}", encoding="utf-8")
    _run("replay", tasks, run_dir, "--snapshot-dir", snapshots, expected=1)
