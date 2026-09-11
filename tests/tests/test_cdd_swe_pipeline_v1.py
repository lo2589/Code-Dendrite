import pytest

from evaluation import run_cdd_swe_pipeline_v1 as pipeline


def test_pipeline_v1_safe_model_name():
    assert pipeline.safe_model_name("glm/GLM-4.5-Air") == "glm__GLM-4.5-Air"


def test_pipeline_v1_refuses_existing_artifacts(tmp_path):
    result_dir = tmp_path / "result"
    result_dir.mkdir()
    with pytest.raises(FileExistsError, match="refuses to overwrite"):
        pipeline.validate_fresh_paths(result_dir, tmp_path / "official.json")


def test_pipeline_v1_summary_keeps_process_and_solve_separate():
    generation = {
        "total": 2,
        "total_success": 2,
        "total_hit": 1,
        "tasks": [
            {
                "cdd_runner_version": "cdd.swebench_runner.v2.4",
                "patch_integrity_version": "cdd.patch_integrity.v2.4",
            },
            {
                "cdd_runner_version": "cdd.swebench_runner.v2.4",
                "patch_integrity_version": "cdd.patch_integrity.v2.4",
            },
        ],
    }
    official = {
        "total_instances": 2,
        "resolved_instances": 1,
        "unresolved_instances": 1,
        "empty_patch_instances": 0,
        "error_instances": 0,
        "resolved_ids": ["a"],
        "unresolved_ids": ["b"],
        "empty_patch_ids": [],
        "error_ids": [],
    }
    summary = pipeline.summarize(
        generation,
        official,
        {
            "patch_error_ids": [],
            "infrastructure_error_ids": [],
            "other_error_ids": [],
        },
    )

    assert summary["solve_rate"] == 0.5
    assert summary["process_metrics"]["valid_diff_instances"] == 2
    assert summary["process_metrics"]["expected_file_hit_instances"] == 1
