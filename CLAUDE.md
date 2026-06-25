# CLAUDE.md — HarborForge

## What this is

**HarborForge** is a pip-installable library (`pip install harborforge`) for mapping evaluation benchmark datasets into [Harbor](https://github.com/laude-institute/harbor)-compatible task directories. It provides the abstract contracts; concrete benchmark adapters live elsewhere (e.g. [g9](https://github.com/altaiiiir/g9)).

## Repo layout

```
harborforge/
  __init__.py       # exports: DataMapper, DatasetHandler, TaskEnrichment
  mapper.py         # DataMapper — abstract base, map(), run(), workers support
  enrichment.py     # TaskEnrichment — Protocol for pre-trial instruction/MCP injection
  run.py            # Generic Harbor trial runner (wraps harbor jobs start)
  registry.py       # generate_registry() — produces registry.json
  handlers/
    base.py         # DatasetHandler contract + verifier helper templates

tests/
  harborforge/      # unit tests for core
```

## Setup

```sh
just setup    # install deps (core + dev)
just test     # run pytest
just format   # ruff + mypy
```

## Key contracts

### DatasetHandler

Subclass this to implement a benchmark dataset type:

| Method | Required | Purpose |
|--------|----------|---------|
| `instruction(task_data)` | ✅ | Content for `instruction.md` — no answer leakage |
| `test_sh(task_data)` | ✅ | Content for `tests/test.sh` — must write float reward to `/logs/verifier/reward.txt` |
| `dockerfile(task_data)` | ✅ | Content for `environment/Dockerfile` |
| `setup()` | optional | Download/prepare data before mapping |
| `data_files(task_data)` | optional | Local files to COPY into the agent's build context |
| `artifacts()` | optional | Container paths to capture after trial |
| `verifier_env_keys()` | optional | Env var keys to forward to the SEPARATE verifier |
| `verifier_dockerfile(task_data)` | optional | Non-None triggers SEPARATE verifier mode |
| `verifier_image_tag(task_data)` | optional | Pre-built image tag to use as FROM in verifier Dockerfile |

### DataMapper

Subclass this to implement a benchmark pipeline:

- `iter_tasks()` — yields `(task_id, dir_name, handler, task_data)` for each task
- `setup()` — optional, called before mapping (downloads, prep)
- `map(output_dir, registry_path, workers)` — writes all task directories; `workers > 1` parallelises with ThreadPoolExecutor
- `run(output_dir, registry_path, workers)` — setup() + map()

### TaskEnrichment

Protocol for injecting extra content into tasks at generation time:

- `extra_instruction(task_data)` — returns markdown to append to `instruction.md`, or `None`
- `mcp_servers(task_data)` — returns list of SSE/HTTP MCP server dicts to add to `task.toml`

## Code style

- `harborforge/` must stay benchmark-agnostic. No benchmark-specific strings, no external dependencies beyond stdlib.
- No comments on obvious code. Comment only on non-obvious invariants or workarounds.
- Type hints on all public APIs.
- Tests mirror package structure in `tests/harborforge/`.
- `just format` before committing — ruff + mypy must pass clean.
