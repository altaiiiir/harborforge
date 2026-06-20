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


def run(
    handler_registry: dict[str, Any],
    *,
    tasks_dir: Path,
    registry_path: Path,
    job_name_prefix: str = "eval",
    default_task: str,
    default_model: str = "anthropic/claude-haiku-4-5-20251001",
) -> None:
    """
    Parse CLI args and run a Harbor job against tasks from this adapter.

    Args:
        handler_registry:  dict mapping dataset_name → DatasetHandler
        tasks_dir:         local directory containing generated Harbor task dirs
        registry_path:     path to this adapter's registry.json
        job_name_prefix:   prefix for generated job names (e.g. "dsgym")
        default_task:      default task or dataset to run (e.g. "daeval/0")
        default_model:     default LLM model in provider/model format
    """
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "task", nargs="?", default=default_task, help="Task (dataset/id) or dataset name"
    )
    parser.add_argument(
        "-m", "--model", default=default_model, help="LLM model (provider/model format)"
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
    args = parser.parse_args()

    task_slug = args.task.replace("/", "__")
    job_name = f"{job_name_prefix}__{task_slug}__{int(time.time()) % 100_000}"
    harbor_bin = Path(sys.executable).parent / "harbor"

    if _is_single_task(args.task):
        task_path = tasks_dir / args.task
        if not task_path.exists():
            raise SystemExit(f"Task not found: {task_path}")
        source_flags = ["-p", str(task_path)]
    else:
        if not registry_path.exists():
            raise SystemExit(f"registry.json not found at {registry_path} — run 'just data' first")
        source_flags = ["-d", args.task.lower(), "--registry-path", str(registry_path)]

    cmd = [
        str(harbor_bin),
        "jobs",
        "start",
        *source_flags,
        "-a",
        "terminus-2",
        "-m",
        args.model,
        "--n-attempts",
        args.n_attempts,
        "--n-concurrent",
        args.n_concurrent,
        "--job-name",
        job_name,
        "-y",
    ]
    if args.n_tasks:
        cmd += ["--n-tasks", args.n_tasks]
    if args.max_turns:
        cmd += ["--ak", f"max_turns={args.max_turns}"]
    if args.force_build:
        cmd += ["--force-build"]

    # Forward handler-declared artifacts and verifier env vars
    dataset_name = args.task.split("/")[0]
    handler = handler_registry.get(dataset_name)

    artifacts = list(args.artifact or [])
    if handler:
        for path in handler.artifacts():
            if path not in artifacts:
                artifacts.append(path)
    for artifact in artifacts:
        cmd += ["--artifact", artifact]

    if handler:
        for key in handler.verifier_env_keys():
            if val := os.environ.get(key):
                cmd += ["--ve", f"{key}={val}"]

    subprocess.run(cmd, check=True)
