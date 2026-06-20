"""Unit tests for harborforge.registry.generate_registry."""

import json
from pathlib import Path

import pytest

from harborforge.registry import generate_registry


def _make_tasks(root: Path, datasets: dict[str, list[str]]) -> None:
    """Create a fake tasks/ tree: {dataset: [task_name, ...]}."""
    for dataset, tasks in datasets.items():
        for task in tasks:
            task_dir = root / dataset / task
            task_dir.mkdir(parents=True)


class TestGenerateRegistry:
    def test_output_path_is_written(self, tmp_path):
        tasks = tmp_path / "tasks"
        out = tmp_path / "registry.json"
        _make_tasks(tasks, {"daeval": ["0", "1"]})
        generate_registry(tasks, out)
        assert out.exists()

    def test_creates_valid_json(self, tmp_path):
        tasks = tmp_path / "tasks"
        out = tmp_path / "registry.json"
        _make_tasks(tasks, {"daeval": ["0", "1"]})
        generate_registry(tasks, out)
        parsed = json.loads(out.read_text())
        assert isinstance(parsed, list)

    def test_groups_tasks_by_parent_dir(self, tmp_path):
        tasks = tmp_path / "tasks"
        out = tmp_path / "registry.json"
        _make_tasks(tasks, {"daeval": ["0", "1"], "dabstep": ["10", "20"]})
        generate_registry(tasks, out)
        parsed = json.loads(out.read_text())
        names = {d["name"] for d in parsed}
        assert "daeval" in names
        assert "dabstep" in names

    def test_task_count_per_dataset(self, tmp_path):
        tasks = tmp_path / "tasks"
        out = tmp_path / "registry.json"
        _make_tasks(tasks, {"daeval": ["0", "1", "2"], "dabstep": ["10"]})
        counts = generate_registry(tasks, out)
        assert counts["daeval"] == 3
        assert counts["dabstep"] == 1

    def test_returns_counts_dict(self, tmp_path):
        tasks = tmp_path / "tasks"
        out = tmp_path / "registry.json"
        _make_tasks(tasks, {"daeval": ["0", "1"]})
        counts = generate_registry(tasks, out)
        assert isinstance(counts, dict)
        assert sum(counts.values()) == 2

    def test_dataset_name_is_lowercased(self, tmp_path):
        tasks = tmp_path / "tasks"
        out = tmp_path / "registry.json"
        _make_tasks(tasks, {"DABStep": ["1", "2"]})
        generate_registry(tasks, out)
        parsed = json.loads(out.read_text())
        assert parsed[0]["name"] == "dabstep"

    def test_empty_dataset_dir_is_skipped(self, tmp_path):
        tasks = tmp_path / "tasks"
        out = tmp_path / "registry.json"
        _make_tasks(tasks, {"daeval": ["0"]})
        (tasks / "empty_dataset").mkdir()  # dataset dir with no tasks
        counts = generate_registry(tasks, out)
        assert "empty_dataset" not in counts

    def test_nonexistent_tasks_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            generate_registry(tmp_path / "nonexistent", tmp_path / "out.json")

    def test_task_schema(self, tmp_path):
        tasks = tmp_path / "tasks"
        out = tmp_path / "registry.json"
        _make_tasks(tasks, {"daeval": ["0"]})
        generate_registry(tasks, out)
        parsed = json.loads(out.read_text())
        dataset = parsed[0]
        assert "name" in dataset
        assert "version" in dataset
        assert "description" in dataset
        assert "tasks" in dataset
        task = dataset["tasks"][0]
        assert "name" in task
        assert "path" in task
