"""
DataMapper — abstract base for benchmark → Harbor task directory pipelines.

Subclass and implement `iter_tasks()`. Override `setup()` to handle data
downloads or prep. Call `run()` as the standard entry point, or `map()`
directly for more control.
"""

import shutil
import stat
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .enrichment import TaskEnrichment
from .handlers.base import DatasetHandler


class DataMapper(ABC):
    """
    Abstract mapper from a benchmark dataset to Harbor task directories.

    Minimal adapter implementation:
      1. Implement `iter_tasks()` to yield tasks.
      2. Optionally override `setup()` to download/prepare raw data.
      3. Call `run()` as the entry point — it handles setup, mapping, and registry.
      4. Optionally pass `enrichments` to inject extra instruction text or MCP servers per task.
    """

    def __init__(self, enrichments: list[TaskEnrichment] | None = None) -> None:
        self.enrichments: list[TaskEnrichment] = enrichments or []

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def setup(self) -> None:
        """Download or prepare raw data before mapping. No-op by default."""

    def map(self, output_dir: Path, registry_path: Path | None = None) -> int:
        """
        Write all tasks to output_dir as Harbor task directories.
        Wipes and recreates output_dir on each call.
        If registry_path is given, auto-generates a Harbor registry.json.
        Returns the number of tasks written.
        """
        if output_dir.exists():
            shutil.rmtree(output_dir)

        total = 0
        current_dataset = ""
        for task_id, dir_name, handler, task_data in self.iter_tasks():
            self._write_task(output_dir / dir_name, task_id, handler, task_data)
            total += 1
            dataset = dir_name.split("/")[0]
            if dataset != current_dataset:
                if current_dataset:
                    print()
                current_dataset = dataset
                print(f"  ↳ {dataset}", end="", flush=True)
            print(f"\r  ↳ {dataset} ({total} written)", end="", flush=True)
        if total:
            print()

        if registry_path is not None:
            from harborforge.registry import generate_registry

            counts = generate_registry(output_dir, registry_path)
            n_datasets = len(counts)
            n_tasks = sum(counts.values())
            print(f"✅ {registry_path} — {n_tasks} tasks across {n_datasets} datasets")

        return total

    def run(self, output_dir: Path, registry_path: Path | None = None) -> None:
        """
        Standard entry point: setup() → map() → optional registry.
        Adapters call this from __main__.py.
        """
        self.setup()
        total = self.map(output_dir, registry_path)
        print(f"📊 Total tasks written: {total}")

    # ---------------------------------------------------------------------------
    # Abstract
    # ---------------------------------------------------------------------------

    @abstractmethod
    def iter_tasks(self) -> Iterator[tuple[str, str, DatasetHandler, dict[str, Any]]]:
        """
        Yield (task_id, dir_name, handler, raw_task_data) for each task.

        - task_id:   unique identifier used in task.toml name field
        - dir_name:  relative path under output_dir (e.g. 'daeval/0')
        - handler:   DatasetHandler instance for this dataset
        - raw_task_data: raw dict from the source benchmark file
        """

    # ---------------------------------------------------------------------------
    # Internal
    # ---------------------------------------------------------------------------

    def _write_task(
        self,
        task_dir: Path,
        task_id: str,
        handler: DatasetHandler,
        task_data: dict[str, Any],
    ) -> None:
        task_dir.mkdir(parents=True, exist_ok=True)

        instruction = handler.instruction(task_data)
        for enrichment in self.enrichments:
            extra = enrichment.extra_instruction(task_data)
            if extra:
                instruction += f"\n\n{extra}"
        (task_dir / "instruction.md").write_text(instruction, encoding="utf-8")

        env_dir = task_dir / "environment"
        env_dir.mkdir(exist_ok=True)

        for local_path, dest_name in handler.data_files(task_data):
            dest = env_dir / dest_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local_path, dest)

        (env_dir / "Dockerfile").write_text(handler.dockerfile(task_data), encoding="utf-8")

        # Auto-detect verifier mode: SEPARATE if handler provides a verifier Dockerfile.
        # Harbor uses tests/ as the verifier build context in SEPARATE mode.
        task_toml = handler.task_toml(task_id)
        verifier_df = handler.verifier_dockerfile(task_data)
        if verifier_df is not None:
            task_toml += "\n[verifier.environment]\nbuild_timeout_sec = 300.0\n"

        for enrichment in self.enrichments:
            for server in enrichment.mcp_servers(task_data):
                task_toml += "\n[[environment.mcp_servers]]\n" + "".join(
                    f'{k} = "{v}"\n' for k, v in server.items()
                )

        (task_dir / "task.toml").write_text(task_toml, encoding="utf-8")

        tests_dir = task_dir / "tests"
        tests_dir.mkdir(exist_ok=True)
        test_sh = tests_dir / "test.sh"
        test_sh.write_text(handler.test_sh(task_data), encoding="utf-8")
        test_sh.chmod(test_sh.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

        # SEPARATE mode: write verifier Dockerfile into tests/ (Harbor's verifier build context).
        # COPY test.sh into the image so Harbor can execute /tests/test.sh inside the container.
        # If verifier_image_tag() is set, use the pre-built image as FROM to skip slow layers.
        if verifier_df is not None:
            image_tag = handler.verifier_image_tag(task_data)
            base = f"FROM {image_tag}" if image_tag else verifier_df.rstrip()
            verifier_df_with_copy = (
                base + "\nCOPY test.sh /tests/test.sh\nRUN chmod +x /tests/test.sh\n"
            )
            (tests_dir / "Dockerfile").write_text(verifier_df_with_copy, encoding="utf-8")
