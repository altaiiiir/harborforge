# CLAUDE.md — g9

## What this is

**g9** maps evaluation benchmark datasets into [Harbor](https://github.com/laude-institute/harbor)-compatible task directories, enabling large-scale parallel agent evaluation.

The core package (`harborforge/`) is benchmark-agnostic. Each benchmark gets its own adapter in `adapters/`. The first reference implementation is DSGym.

## Repo layout

```
harborforge/          # pip-installable core — abstract contracts only
  mapper.py           # DataMapper base class (setup, map, run)
  run.py              # Generic Harbor trial runner (wraps harbor jobs start)
  registry.py         # generate_registry() — produces registry.json
  handlers/
    base.py           # DatasetHandler base class + verifier templates

adapters/             # concrete benchmark implementations
  dsgym/
    mapper.py         # DSGymMapper(DataMapper)
    base_image.py     # BASE_IMAGE_NAME, BASE_IMAGE constants
    eval.Dockerfile   # shared base Docker image — built by `just build-base`
    run_trial.py      # thin wrapper: calls harborforge.run with DSGym config
    handlers/         # one file per DSGym dataset type
    download.py       # Kaggle dataset downloader

tests/
  harborforge/        # unit + integration tests for core
  adapters/dsgym/     # tests for the DSGym adapter

tools/
  benchmark_builds.py # Docker build-time benchmark (base image vs no base)

.data/                # local data (gitignored)
  task/               # raw DSGym task files (.json / .jsonl)
  data/               # raw data files (CSVs, .h5ad, etc.)
  tasks/              # generated Harbor task directories
```

## Setup

```sh
pip install uv          # Python package manager
brew install just       # task runner

just setup              # create venv + install deps + download data
just build-base         # build shared Docker base image (run once)
just data               # download raw data + run mapper → .data/tasks/
```

Credentials go in `.env` (gitignored):
```
ANTHROPIC_API_KEY=sk-ant-...
KAGGLE_TOKEN=KGAT_...      # for DSPredict tasks
```

## Running things

```sh
just trial daeval/0               # single task
just trial daeval -l 20           # 20 tasks from a dataset
just trial dspredict/titanic      # Kaggle competition task
just trial daeval/0 -k 3          # 3 attempts
just test                         # pytest
just format                       # ruff + mypy
just view                         # open Harbor trajectory viewer
just benchmark                    # Docker build-time benchmark
```

## Adding a new benchmark adapter

1. Create `adapters/<name>/` with:
   - `handlers/` — one `DatasetHandler` subclass per dataset type
   - `mapper.py` — `DataMapper` subclass implementing `iter_tasks()`
   - `__main__.py` — calls `DataMapper().run(output_dir, registry_path)`
   - `run_trial.py` — calls `harborforge.run.run()` with your registry

2. Implement the handler contract (see table below).

3. Add a `just data <name>` call — the existing recipe dispatches to `python -m adapters.<name>`.

See `adapters/dsgym/` as the reference implementation.

## Handler contract

Every handler subclasses `harborforge.handlers.DatasetHandler`:

| Method | Required | Purpose |
|--------|----------|---------|
| `instruction(task_data)` | ✅ | Content for `instruction.md` — no answer leakage |
| `test_sh(task_data)` | ✅ | Content for `tests/test.sh` — must write float reward to `/logs/verifier/reward.txt` |
| `dockerfile(task_data)` | ✅ | Content for `environment/Dockerfile` |
| `setup()` | optional | Download/prepare data for this dataset |
| `data_files(task_data)` | optional | Local files to COPY into the image build context |
| `artifacts()` | optional | Container paths to capture after trial |
| `verifier_env_keys()` | optional | Env var keys to forward to the SEPARATE verifier |
| `verifier_dockerfile(task_data)` | optional | Non-None triggers SEPARATE verifier mode |

## Harbor task contract

Each generated task directory must contain:

```
<task>/
├── instruction.md          # shown to the agent (no answer)
├── task.toml               # Harbor config (timeouts, env)
├── environment/
│   └── Dockerfile          # agent container — data files go here
└── tests/
    ├── test.sh             # verifier script — writes reward to /logs/verifier/reward.txt
    └── Dockerfile          # (SEPARATE mode only) verifier container
```

## Verifier modes

**SHARED** (default): verifier runs inside the agent container after the agent finishes.

**SEPARATE**: verifier runs in its own isolated container. Triggered when `handler.verifier_dockerfile()` returns non-None. Harbor re-materializes agent artifacts at their original source paths inside the verifier container — e.g. `/app/submission.csv` in the agent maps to `/app/submission.csv` in the verifier.

## Code style

- Simple and concise over clever. Three similar lines beat a premature abstraction.
- No comments on obvious code. Only comment on non-obvious invariants or workarounds.
- No dead code. No backwards-compat shims, no unused parameters.
- Validate at system boundaries only. Trust internal code.
- Type hints on all public APIs.
- `harborforge/` must stay benchmark-agnostic. No benchmark-specific strings belong there.
- Base image: always import `BASE_IMAGE` from `adapters/<name>/base_image.py`. Never hardcode `FROM python:...` in handlers.

## Python conventions

- Python 3.13+, managed with `uv`.
- `pyproject.toml` is the source of truth for dependencies.
- Tests live in `tests/`, mirror the package structure, use `pytest`.
- Formatters: `ruff` for linting/formatting, `mypy` for types. Run `just format` before committing.
