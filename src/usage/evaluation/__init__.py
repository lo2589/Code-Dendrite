"""Reproducible CDD evidence snapshots, offline replay, and evaluation reports.

Dataset contract (``cdd replay``)::

    {"tasks": [{"instance_id": "case-1", "root": "/repo", "issue": "...",
                "expected_files": ["pkg/foo.py"], "official_resolved": true}]}

``root`` and ``issue`` may be omitted when a snapshot supplies them. Official
outcomes are imported only when provided; the tool never infers them from CDD.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from usage.packets.issue_evidence_packet import (
    generate_issue_evidence_packet,
    validate_issue_evidence_packet,
)

SNAPSHOT_VERSION = "codedendrite_snapshot_v1"
REPORT_VERSION = "codedendrite_evaluation_v1"
INDEX_FILES = ("anchors.json", "relations.json", "module_tree.json", "module_tree_v2.json")
INSTANCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON object required: {path}")
    return data


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(root: Path, *args: str) -> str:
    run = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    if run.returncode:
        raise ValueError(run.stderr.strip() or f"git {' '.join(args)} failed")
    return run.stdout.strip()


def create_snapshot(
    root: str, issue_file: str, output_dir: str, instance_id: str,
    base_commit: str | None = None,
) -> Path:
    """Save an immutable index + issue + packet tied to a clean Git HEAD."""
    if not INSTANCE_RE.fullmatch(instance_id):
        raise ValueError("instance_id must be a safe one-component identifier")
    project = Path(root).expanduser().resolve()
    issue_path = Path(issue_file).expanduser().resolve()
    issue_text = issue_path.read_text(encoding="utf-8")
    head = _git(project, "rev-parse", "HEAD")
    if base_commit and _git(project, "rev-parse", base_commit) != head:
        raise ValueError("base_commit must resolve to the current HEAD")
    # Generated index files may be untracked in a fresh repository. Source
    # edits and other untracked files still invalidate a commit-bound snapshot.
    status = _git(project, "status", "--porcelain", "--untracked-files=all", "--", ".")
    dirty = []
    for line in status.splitlines():
        relative = line[3:].strip().strip('"')
        if relative.startswith(".codedendrite/") or relative.startswith((".code_genome_db", ".code_hash_db")):
            continue
        dirty.append(relative)
    if dirty:
        raise ValueError("project has uncommitted files; commit or remove them before snapshot")

    # Refresh the index against the exact source tree that HEAD names.
    subprocess.run(
        [sys.executable, "-m", "usage.cli", str(project), "--update"],
        check=True, stdout=subprocess.DEVNULL,
    )
    source_index = project / ".codedendrite"
    for name in INDEX_FILES[:2]:
        if not (source_index / name).is_file():
            raise ValueError(f"index is incomplete: missing {name}")

    destination = Path(output_dir).expanduser().resolve() / instance_id
    if destination.exists():
        raise FileExistsError(f"snapshot already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix=f".{instance_id}-", dir=destination.parent))
    try:
        (scratch / "index").mkdir()
        hashes = {}
        for name in INDEX_FILES:
            source = source_index / name
            if source.exists():
                target = scratch / "index" / name
                shutil.copy2(source, target)
                hashes[name] = _sha256(target)
        (scratch / "issue.md").write_text(issue_text, encoding="utf-8")
        packet = generate_issue_evidence_packet(issue_text, root=str(project))
        _write_json(scratch / "packet.json", packet)
        _write_json(scratch / "manifest.json", {
            "version": SNAPSHOT_VERSION,
            "instance_id": instance_id,
            "base_commit": head,
            "project_root": str(project),
            "issue_sha256": _sha256(scratch / "issue.md"),
            "packet_sha256": _sha256(scratch / "packet.json"),
            "index_sha256": hashes,
        })
        scratch.rename(destination)
    except Exception:
        shutil.rmtree(scratch, ignore_errors=True)
        raise
    return destination


def _packet_files(packet: dict) -> list[str]:
    validate_issue_evidence_packet(packet)
    navigation = packet.get("navigation") or {}
    return sorted({str(file_name) for file_name in navigation.get("candidate_files", [])})


def _tasks(path: Path) -> list[dict]:
    data = _read_json(path)
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("tasks JSON needs a non-empty tasks array")
    seen = set()
    for task in tasks:
        if not isinstance(task, dict) or not INSTANCE_RE.fullmatch(str(task.get("instance_id", ""))):
            raise ValueError("every task needs a safe instance_id")
        if task["instance_id"] in seen:
            raise ValueError(f"duplicate instance_id: {task['instance_id']}")
        seen.add(task["instance_id"])
        if "expected_files" in task and not (
            isinstance(task["expected_files"], list)
            and all(isinstance(item, str) for item in task["expected_files"])
        ):
            raise ValueError("expected_files must be a list of paths")
        if "official_resolved" in task and not isinstance(task["official_resolved"], bool):
            raise ValueError("official_resolved must be a boolean")
    return tasks


def replay(
    tasks_file: str, run_dir: str, output: str | None = None,
    snapshot_dir: str | None = None,
) -> Path:
    """Compare recorded and current evidence packets without editing source."""
    task_path = Path(tasks_file).expanduser().resolve()
    run_path = Path(run_dir).expanduser().resolve()
    snapshots = Path(snapshot_dir).expanduser().resolve() if snapshot_dir else None
    cases = []
    for task in _tasks(task_path):
        ident = task["instance_id"]
        base = (snapshots or run_path) / ident
        old_packet_path = base / "packet.json"
        old_packet = _read_json(old_packet_path)
        manifest_path = base / "manifest.json"
        manifest = _read_json(manifest_path) if manifest_path.exists() else {}
        if manifest and manifest.get("version") != SNAPSHOT_VERSION:
            raise ValueError(f"unsupported snapshot version: {manifest_path}")
        if manifest and manifest.get("instance_id") != ident:
            raise ValueError(f"snapshot instance does not match task: {ident}")
        if manifest and manifest.get("packet_sha256") != _sha256(old_packet_path):
            raise ValueError(f"recorded packet changed after snapshot: {old_packet_path}")
        if manifest:
            index_hashes = manifest.get("index_sha256")
            if not isinstance(index_hashes, dict):
                raise ValueError(f"snapshot has no index hashes: {manifest_path}")
            for name, expected_hash in index_hashes.items():
                index_file = base / "index" / name
                if name not in INDEX_FILES or not index_file.is_file() or _sha256(index_file) != expected_hash:
                    raise ValueError(f"recorded index changed after snapshot: {index_file}")
        root = task.get("root") or manifest.get("project_root")
        if not root:
            raise ValueError(f"task {ident} needs root or a snapshot manifest")
        issue = task.get("issue")
        if issue is None:
            issue_path = base / "issue.md"
            issue = issue_path.read_text(encoding="utf-8")
            if manifest and manifest.get("issue_sha256") != _sha256(issue_path):
                raise ValueError(f"recorded issue changed after snapshot: {issue_path}")
        if not isinstance(issue, str) or not issue.strip():
            raise ValueError(f"task {ident} needs non-empty issue text")
        new_packet = generate_issue_evidence_packet(issue, root=str(Path(root).resolve()))
        old_files = _packet_files(old_packet)
        new_files = _packet_files(new_packet)
        expected = task.get("expected_files")
        cases.append({
            "instance_id": ident,
            "generation": {"recorded_valid": True, "current_valid": True},
            "localization": {
                "recorded_files": old_files, "current_files": new_files,
                "expected_files": expected,
                "recorded_hit": bool(set(old_files) & set(expected)) if expected is not None else None,
                "current_hit": bool(set(new_files) & set(expected)) if expected is not None else None,
                "changed": old_files != new_files,
            },
            "official": {"resolved": task.get("official_resolved")},
        })
    report = {"version": REPORT_VERSION, "cases": cases}
    report["summary"] = summarize_report(report)
    target = Path(output).expanduser().resolve() if output else run_path / "replay-report.json"
    _write_json(target, report)
    return target


def summarize_report(report: dict) -> dict:
    """Keep generation, localization, and official outcomes in separate lanes."""
    cases = report["cases"]
    known = [case for case in cases if case["localization"]["expected_files"] is not None]
    official = [case for case in cases if case["official"]["resolved"] is not None]
    return {
        "total": len(cases),
        "generation": {
            "recorded_valid": sum(case["generation"]["recorded_valid"] for case in cases),
            "current_valid": sum(case["generation"]["current_valid"] for case in cases),
        },
        "localization": {
            "labeled": len(known),
            "recorded_hit": sum(case["localization"]["recorded_hit"] for case in known),
            "current_hit": sum(case["localization"]["current_hit"] for case in known),
            "changed": sum(case["localization"]["changed"] for case in cases),
        },
        "official": {
            "known": len(official),
            "resolved": sum(case["official"]["resolved"] for case in official),
        },
    }


def validate_report(report: dict) -> dict:
    """Validate the report contract and recompute every published count."""
    if report.get("version") != REPORT_VERSION:
        raise ValueError(f"unsupported report version: {report.get('version')}")
    cases = report.get("cases")
    if not isinstance(cases, list):
        raise ValueError("report cases must be a list")
    seen = set()
    for case in cases:
        if not isinstance(case, dict) or not INSTANCE_RE.fullmatch(str(case.get("instance_id", ""))):
            raise ValueError("each case needs a safe instance_id")
        if case["instance_id"] in seen:
            raise ValueError(f"duplicate case: {case['instance_id']}")
        seen.add(case["instance_id"])
        generation = case.get("generation")
        localization = case.get("localization")
        official = case.get("official")
        if not isinstance(generation, dict) or not all(
            isinstance(generation.get(key), bool) for key in ("recorded_valid", "current_valid")
        ):
            raise ValueError("generation lane needs two boolean validity fields")
        if not isinstance(localization, dict) or not all(
            isinstance(localization.get(key), list)
            and all(isinstance(value, str) for value in localization[key])
            for key in ("recorded_files", "current_files")
        ):
            raise ValueError("localization lane needs recorded/current file lists")
        expected = localization.get("expected_files")
        if expected is not None and not (
            isinstance(expected, list) and all(isinstance(value, str) for value in expected)
        ):
            raise ValueError("expected_files must be a path list or null")
        for key in ("recorded_hit", "current_hit"):
            hit = localization.get(key)
            if hit is not None and not isinstance(hit, bool):
                raise ValueError(f"{key} must be boolean or null")
            if hit != (bool(set(localization[key.split('_')[0] + '_files']) & set(expected)) if expected is not None else None):
                raise ValueError(f"{key} disagrees with the file sets")
        if localization.get("changed") != (localization["recorded_files"] != localization["current_files"]):
            raise ValueError("changed disagrees with file sets")
        if not isinstance(official, dict) or official.get("resolved") is not None and not isinstance(official["resolved"], bool):
            raise ValueError("official resolved must be boolean or null")
    summary = summarize_report(report)
    if report.get("summary") != summary:
        raise ValueError("summary disagrees with case data")
    return summary


__all__ = [
    "SNAPSHOT_VERSION", "REPORT_VERSION", "create_snapshot", "replay",
    "summarize_report", "validate_report",
]
