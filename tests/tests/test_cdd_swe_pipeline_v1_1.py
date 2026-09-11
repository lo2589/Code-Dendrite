import pytest

from evaluation import run_cdd_swe_pipeline_v1_1 as pipeline


def test_pipeline_v1_1_preserves_absolute_symlink(tmp_path):
    target = tmp_path / "python-target"
    target.write_text("", encoding="utf-8")
    link = tmp_path / "venv-python"
    link.symlink_to(target)

    assert pipeline.resolve_path(str(link)) == link
    assert pipeline.resolve_path(str(link)) != target


def test_pipeline_v1_1_validates_reused_generation():
    generated = {
        "total": 2,
        "tasks": [
            {"cdd_runner_version": "cdd.swebench_runner.v2.4"},
            {"cdd_runner_version": "cdd.swebench_runner.v2.4"},
        ],
    }
    pipeline.validate_generation(generated, 2, "cdd.swebench_runner.v2.4")


def test_pipeline_v1_1_rejects_wrong_generation_version():
    generated = {
        "total": 1,
        "tasks": [{"cdd_runner_version": "cdd.swebench_runner.v2.3"}],
    }
    with pytest.raises(RuntimeError, match="Runner version mismatch"):
        pipeline.validate_generation(generated, 1, "cdd.swebench_runner.v2.4")
