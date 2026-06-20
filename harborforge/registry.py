"""
Generate a local Harbor registry.json from a directory of Harbor task directories.

The tasks directory is expected to have the structure:
    tasks_dir/
        dataset_a/
            task_0/
            task_1/
        dataset_b/
            task_0/

Each top-level subdirectory becomes a named dataset in the registry.
"""

import json
from pathlib import Path


def generate_registry(
    tasks_dir: Path,
    output_path: Path,
    version: str = "1.0",
    description_template: str = "{name} benchmark tasks",
) -> dict[str, int]:
    """
    Scan tasks_dir and write a Harbor registry.json to output_path.

    Returns a dict of {dataset_name: task_count}.
    """
    if not tasks_dir.exists():
        raise FileNotFoundError(f"Tasks directory not found: {tasks_dir}")

    datasets = []
    counts: dict[str, int] = {}

    for dataset_dir in sorted(tasks_dir.iterdir()):
        if not dataset_dir.is_dir():
            continue

        tasks = [
            {"name": task.name, "path": str(task)}
            for task in sorted(dataset_dir.iterdir())
            if task.is_dir()
        ]

        if not tasks:
            continue

        name = dataset_dir.name.lower()
        datasets.append(
            {
                "name": name,
                "version": version,
                "description": description_template.format(name=dataset_dir.name),
                "tasks": tasks,
            }
        )
        counts[name] = len(tasks)

    output_path.write_text(json.dumps(datasets, indent=2))
    return counts
