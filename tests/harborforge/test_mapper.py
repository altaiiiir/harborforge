"""Unit tests for harborforge.mapper — DataMapper base class and task directory writing."""

import stat
import tomllib
from collections.abc import Iterator
from typing import Any

from harborforge import DataMapper
from harborforge.handlers.base import DatasetHandler, exact_match_verifier

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _StubHandler(DatasetHandler):
    dataset_name = "stub"

    def instruction(self, task_data: dict[str, Any]) -> str:
        return task_data.get("instruction", "default instruction")

    def test_sh(self, task_data: dict[str, Any]) -> str:
        return exact_match_verifier(task_data.get("answer", ""))

    def dockerfile(self, task_data: dict[str, Any]) -> str:
        return "FROM python:3.11-slim\n\nWORKDIR /app\n"


class _StubMapper(DataMapper):
    def __init__(self, tasks: list[tuple[str, str, DatasetHandler, dict]]):
        self._tasks = tasks

    def iter_tasks(self) -> Iterator[tuple[str, str, DatasetHandler, dict[str, Any]]]:
        yield from self._tasks


_HANDLER = _StubHandler()


def _make_mapper(*tasks):
    return _StubMapper(list(tasks))


# ---------------------------------------------------------------------------
# Directory structure
# ---------------------------------------------------------------------------


class TestMapperDirectoryStructure:
    def test_creates_instruction_md(self, tmp_path):
        mapper = _make_mapper(("t/0", "t/0", _HANDLER, {"instruction": "Do X"}))
        mapper.map(tmp_path)
        assert (tmp_path / "t/0/instruction.md").exists()

    def test_creates_task_toml(self, tmp_path):
        mapper = _make_mapper(("t/0", "t/0", _HANDLER, {}))
        mapper.map(tmp_path)
        assert (tmp_path / "t/0/task.toml").exists()

    def test_creates_dockerfile(self, tmp_path):
        mapper = _make_mapper(("t/0", "t/0", _HANDLER, {}))
        mapper.map(tmp_path)
        assert (tmp_path / "t/0/environment/Dockerfile").exists()

    def test_creates_test_sh(self, tmp_path):
        mapper = _make_mapper(("t/0", "t/0", _HANDLER, {}))
        mapper.map(tmp_path)
        assert (tmp_path / "t/0/tests/test.sh").exists()

    def test_test_sh_is_executable(self, tmp_path):
        mapper = _make_mapper(("t/0", "t/0", _HANDLER, {}))
        mapper.map(tmp_path)
        mode = (tmp_path / "t/0/tests/test.sh").stat().st_mode
        assert mode & stat.S_IEXEC

    def test_multiple_tasks(self, tmp_path):
        mapper = _make_mapper(
            ("a/0", "a/0", _HANDLER, {}),
            ("a/1", "a/1", _HANDLER, {}),
            ("b/0", "b/0", _HANDLER, {}),
        )
        count = mapper.map(tmp_path)
        assert count == 3
        assert (tmp_path / "a/0").is_dir()
        assert (tmp_path / "a/1").is_dir()
        assert (tmp_path / "b/0").is_dir()

    def test_wipes_output_dir_on_rerun(self, tmp_path):
        mapper = _make_mapper(("t/0", "t/0", _HANDLER, {}))
        mapper.map(tmp_path)
        (tmp_path / "stale_file.txt").write_text("stale")
        mapper.map(tmp_path)
        assert not (tmp_path / "stale_file.txt").exists()


# ---------------------------------------------------------------------------
# File content
# ---------------------------------------------------------------------------


class TestMapperFileContent:
    def test_instruction_md_content(self, tmp_path):
        mapper = _make_mapper(("t/0", "t/0", _HANDLER, {"instruction": "Solve this"}))
        mapper.map(tmp_path)
        content = (tmp_path / "t/0/instruction.md").read_text()
        assert "Solve this" in content

    def test_task_toml_is_valid(self, tmp_path):
        mapper = _make_mapper(("my/task-1", "my/task-1", _HANDLER, {}))
        mapper.map(tmp_path)
        toml_str = (tmp_path / "my/task-1/task.toml").read_text()
        parsed = tomllib.loads(toml_str)
        assert "verifier" in parsed

    def test_task_toml_contains_task_id(self, tmp_path):
        mapper = _make_mapper(("my/task-1", "my/task-1", _HANDLER, {}))
        mapper.map(tmp_path)
        toml_str = (tmp_path / "my/task-1/task.toml").read_text()
        assert "my/task-1" in toml_str

    def test_test_sh_contains_reward_path(self, tmp_path):
        mapper = _make_mapper(("t/0", "t/0", _HANDLER, {"answer": "42"}))
        mapper.map(tmp_path)
        content = (tmp_path / "t/0/tests/test.sh").read_text()
        assert "/logs/verifier/reward.txt" in content

    def test_answer_not_in_instruction(self, tmp_path):
        mapper = _make_mapper(("t/0", "t/0", _HANDLER, {"instruction": "Q?", "answer": "SECRET"}))
        mapper.map(tmp_path)
        instruction = (tmp_path / "t/0/instruction.md").read_text()
        assert "SECRET" not in instruction


# ---------------------------------------------------------------------------
# Data files
# ---------------------------------------------------------------------------


class TestMapperDataFiles:
    def test_data_files_copied_to_environment(self, tmp_path):
        source_file = tmp_path / "source.csv"
        source_file.write_text("a,b\n1,2")

        class _HandlerWithData(_StubHandler):
            def data_files(self, task_data):
                return [(source_file, "data/source.csv")]

        mapper = _StubMapper([("t/0", "t/0", _HandlerWithData(), {})])
        output = tmp_path / "out"
        mapper.map(output)
        assert (output / "t/0/environment/data/source.csv").exists()


# ---------------------------------------------------------------------------
# SEPARATE verifier mode
# ---------------------------------------------------------------------------


class _HandlerWithVerifier(_StubHandler):
    def verifier_dockerfile(self, task_data):
        return "FROM python:3.11-slim\nWORKDIR /verifier\n"


class TestMapperSeparateVerifier:
    def test_separate_verifier_writes_verifier_dockerfile(self, tmp_path):
        mapper = _StubMapper([("t/0", "t/0", _HandlerWithVerifier(), {})])
        mapper.map(tmp_path)
        assert (tmp_path / "t/0/tests/Dockerfile").exists()

    def test_separate_verifier_task_toml_has_verifier_environment(self, tmp_path):
        mapper = _StubMapper([("t/0", "t/0", _HandlerWithVerifier(), {})])
        mapper.map(tmp_path)
        toml = (tmp_path / "t/0/task.toml").read_text()
        assert "[verifier.environment]" in toml

    def test_shared_mode_has_no_verifier_environment(self, tmp_path):
        mapper = _make_mapper(("t/0", "t/0", _HANDLER, {}))
        mapper.map(tmp_path)
        toml = (tmp_path / "t/0/task.toml").read_text()
        assert "[verifier.environment]" not in toml
