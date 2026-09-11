import copy
import sys
from pathlib import Path

import pytest


ROOT = str(Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from evaluation.contract import ContractError, new_report, summarize_report, validate_report


def _report(count=2):
    return new_report(
        ["task-{}".format(index) for index in range(count)],
        run_id="mini25-evidence-gate",
        suite="swebench_lite",
        model="MiniMax-M2.5",
        taskpackage_variant="cdd-evidence-gated",
    )


def _complete_generation(task, *, valid_diff, file_hit):
    task["execution_status"] = "complete"
    task["outcome"]["valid_diff"] = valid_diff
    task["outcome"]["expected_file_hit"] = file_hit
    task["navigation"].update({
        "commands_total": 4,
        "commands_repeated": 1,
        "max_turns_exhausted": False,
        "ambiguous_auto_expands": 0,
    })


def test_pending_template_is_valid_and_keeps_official_rate_null():
    report = _report(25)
    summary = summarize_report(report)
    assert report["run"]["task_count"] == 25
    assert summary["official"]["resolved_rate"] is None
    assert summary["official"]["comparable"] is False
    assert summary["navigation"]["command_repeat_rate"] is None
    assert summary["navigation"]["ambiguous_auto_expands"] is None


def test_valid_diff_and_file_hit_never_imply_official_resolution():
    report = _report(1)
    _complete_generation(report["tasks"][0], valid_diff=True, file_hit=True)
    summary = summarize_report(report)
    assert summary["generation"]["valid_diff_count"] == 1
    assert summary["generation"]["expected_file_hit_count"] == 1
    assert summary["official"]["resolved_count"] == 0
    assert summary["official"]["resolved_rate"] is None


def test_complete_harness_requires_every_official_result():
    report = _report(2)
    report["run"]["official_harness"]["status"] = "complete"
    with pytest.raises(ContractError, match="requires resolved/unresolved for every task"):
        validate_report(report)


def test_complete_harness_produces_comparable_rate():
    report = _report(2)
    for task in report["tasks"]:
        _complete_generation(task, valid_diff=True, file_hit=True)
    report["run"]["official_harness"] = {
        "status": "complete", "report_path": "reports/official.json",
    }
    report["tasks"][0]["outcome"].update({"official_status": "resolved", "official_resolved": True})
    report["tasks"][1]["outcome"].update({"official_status": "unresolved", "official_resolved": False})
    summary = summarize_report(report)
    assert summary["official"]["resolved_rate"] == 0.5
    assert summary["official"]["comparable"] is True


@pytest.mark.parametrize("field", ["success", "success_rate", "solve_rate"])
def test_ambiguous_success_fields_are_forbidden(field):
    report = _report(1)
    report[field] = 1
    with pytest.raises(ContractError, match="is forbidden"):
        validate_report(report)


def test_ambiguous_navigation_must_not_auto_expand():
    report = _report(1)
    report["tasks"][0]["navigation"]["ambiguous_auto_expands"] = 1
    with pytest.raises(ContractError, match="must be 0"):
        validate_report(report)


def test_repeated_commands_cannot_exceed_total():
    report = _report(1)
    _complete_generation(report["tasks"][0], valid_diff=False, file_hit=False)
    report["tasks"][0]["navigation"]["commands_repeated"] = 5
    with pytest.raises(ContractError, match="cannot exceed"):
        validate_report(report)
