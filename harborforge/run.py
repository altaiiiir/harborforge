"""
Generic Harbor trial runner.

Wraps `harbor jobs start` with handler-aware artifact/credential forwarding.
Adapters call `run()` with their registry, tasks dir, and defaults.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def _is_single_task(task: str) -> bool:
    """True when task is a specific task (dataset/id), False when it's a dataset name."""
    return "/" in task


def build_job_cmd(
    handler_registry: dict[str, Any],
    *,
    tasks_dir: Path,
    registry_path: Path,
    task: str,
    model: str,
    n_attempts: str = "1",
    n_concurrent: str = "4",
    n_tasks: str | None = None,
    max_turns: str | None = None,
    force_build: bool = False,
    artifacts: list[str] | None = None,
    agent: str = "terminus-2",
    job_name_prefix: str = "eval",
    job_name: str | None = None,
    harbor_bin: Path | None = None,
    extra_args: list[str] | None = None,
) -> list[str]:
    """Build a `harbor jobs start` argv with handler-aware artifact/verifier forwarding."""
    dataset_name = task.split("/")[0]

    if _is_single_task(task):
        task_path = tasks_dir / task
        if not task_path.exists():
            raise SystemExit(f"Task not found: {task_path}")
        source_flags = ["-p", str(task_path), "-d", dataset_name]
    else:
        if not registry_path.exists():
            raise SystemExit(f"registry.json not found at {registry_path} — run 'just data' first")
        source_flags = ["-d", task.lower(), "--registry-path", str(registry_path)]

    if job_name is None:
        task_slug = task.replace("/", "__")
        job_name = f"{job_name_prefix}__{task_slug}__{time.time_ns()}"

    cmd = [
        str(harbor_bin or Path(sys.executable).parent / "harbor"),
        "jobs",
        "start",
        *source_flags,
        "-a",
        agent,
        "-m",
        model,
        "--n-attempts",
        n_attempts,
        "--n-concurrent",
        n_concurrent,
        "--job-name",
        job_name,
        "-y",
    ]
    if n_tasks:
        cmd += ["--n-tasks", n_tasks]
    if max_turns:
        cmd += ["--ak", f"max_turns={max_turns}"]
    if force_build:
        cmd += ["--force-build"]

    merged_artifacts = list(artifacts or [])
    handler = handler_registry.get(dataset_name)
    if handler:
        for path in handler.artifacts():
            if path not in merged_artifacts:
                merged_artifacts.append(path)
    for artifact in merged_artifacts:
        cmd += ["--artifact", artifact]

    if handler:
        for key in handler.verifier_env_keys():
            if val := os.environ.get(key):
                cmd += ["--ve", f"{key}={val}"]

    if extra_args:
        cmd.extend(extra_args)

    return cmd


def run(
    handler_registry: dict[str, Any],
    *,
    tasks_dir: Path,
    registry_path: Path,
    job_name_prefix: str = "eval",
    default_task: str,
    default_model: str = "anthropic/claude-haiku-4-5-20251001",
    default_agent: str = "terminus-2",
) -> None:
    """
    Parse CLI args and run a Harbor job against tasks from this adapter.

    Unknown flags are forwarded to `harbor jobs start` (e.g. `--env gke`, `--ek ...`).
    """
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "task", nargs="?", default=default_task, help="Task (dataset/id) or dataset name"
    )
    parser.add_argument(
        "-m", "--model", default=default_model, help="LLM model (provider/model format)"
    )
    parser.add_argument(
        "-a",
        "--agent",
        default=default_agent,
        help="Harbor agent name (default: terminus-2)",
    )
    parser.add_argument("-k", "--n-attempts", default="1", help="Attempts per task (default: 1)")
    parser.add_argument("-n", "--n-concurrent", default="4", help="Concurrent trials (default: 4)")
    parser.add_argument("-l", "--n-tasks", help="Max tasks to run from dataset")
    parser.add_argument("--max-turns", help="Max agent turns")
    parser.add_argument("--force-build", action="store_true", help="Force Docker image rebuild")
    parser.add_argument(
        "--artifact",
        action="append",
        metavar="PATH",
        help="Container path to capture as artifact (repeatable)",
    )
    args, extra_args = parser.parse_known_args()

    cmd = build_job_cmd(
        handler_registry,
        tasks_dir=tasks_dir,
        registry_path=registry_path,
        task=args.task,
        model=args.model,
        agent=args.agent,
        n_attempts=args.n_attempts,
        n_concurrent=args.n_concurrent,
        n_tasks=args.n_tasks,
        max_turns=args.max_turns,
        force_build=args.force_build,
        artifacts=args.artifact,
        job_name_prefix=job_name_prefix,
        extra_args=extra_args,
    )
    subprocess.run(cmd, check=True)
