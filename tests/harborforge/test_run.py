"""Unit tests for harborforge.run."""

from pathlib import Path

from harborforge.run import _is_single_task, build_job_cmd


class _StubHandler:
    def artifacts(self) -> list[str]:
        return ["/app/submission.csv"]

    def verifier_env_keys(self) -> list[str]:
        return ["KAGGLE_TOKEN"]


class TestIsSingleTask:
    def test_dataset_slash_id_is_single(self):
        assert _is_single_task("daeval/0") is True

    def test_dabstep_slash_id_is_single(self):
        assert _is_single_task("DABStep/123") is True

    def test_deep_path_is_single(self):
        assert _is_single_task("dspredict/house-prices-advanced-regression-techniques") is True

    def test_dataset_name_is_not_single(self):
        assert _is_single_task("daeval") is False

    def test_discovery_is_not_single(self):
        assert _is_single_task("discovery") is False

    def test_empty_string_is_not_single(self):
        assert _is_single_task("") is False


class TestBuildJobCmd:
    def test_forwards_extra_harbor_args(self, tmp_path, monkeypatch):
        tasks_dir = tmp_path / "tasks"
        task_dir = tasks_dir / "daeval" / "0"
        task_dir.mkdir(parents=True)
        registry_path = tmp_path / "registry.json"
        registry_path.write_text("{}")

        monkeypatch.setenv("KAGGLE_TOKEN", "secret")

        cmd = build_job_cmd(
            {"daeval": _StubHandler()},
            tasks_dir=tasks_dir,
            registry_path=registry_path,
            task="daeval/0",
            model="anthropic/claude-haiku-4-5-20251001",
            job_name="test-job",
            harbor_bin=Path("/usr/bin/harbor"),
            extra_args=["--env", "gke", "--ek", "cluster_name=foo"],
        )

        assert cmd[0] == "/usr/bin/harbor"
        assert "-p" in cmd and str(task_dir) in cmd
        assert "--artifact" in cmd and "/app/submission.csv" in cmd
        assert "--ve" in cmd and "KAGGLE_TOKEN=secret" in cmd
        assert cmd[-4:] == ["--env", "gke", "--ek", "cluster_name=foo"]

    def test_agent_flag(self, tmp_path):
        tasks_dir = tmp_path / "tasks"
        task_dir = tasks_dir / "daeval" / "0"
        task_dir.mkdir(parents=True)
        registry_path = tmp_path / "registry.json"
        registry_path.write_text("{}")

        cmd = build_job_cmd(
            {},
            tasks_dir=tasks_dir,
            registry_path=registry_path,
            task="daeval/0",
            model="ollama/qwen2.5:7b",
            agent="terminus-2",
            job_name="test-job",
            harbor_bin=Path("/usr/bin/harbor"),
        )

        a_idx = cmd.index("-a")
        assert cmd[a_idx + 1] == "terminus-2"
