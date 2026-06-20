# HarborForge

[![CI](https://github.com/altaiiiir/harborforge/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/altaiiiir/harborforge/actions/workflows/ci.yml) [![Downloads](https://img.shields.io/pypi/dt/harborforge)](https://pypi.org/project/harborforge/)

Forge [Harbor](https://github.com/laude-institute/harbor) task directories from any evaluation benchmark.

HarborForge provides the abstract contracts (`DataMapper`, `DatasetHandler`) for turning raw benchmark datasets into Harbor-compatible task directories, enabling large-scale parallel agent evaluation.

## How it works

```
Raw benchmark data
      ↓  DataMapper.map()
Harbor task directories
      ↓  harbor jobs start
Agent runs in isolated Docker container
      ↓
Verifier scores the output → reward written to Harbor
```

Each task directory contains an `instruction.md` (shown to the agent), a `Dockerfile` (the agent's environment), and a `test.sh` verifier that writes a float reward to `/logs/verifier/reward.txt`.

## Installation

```sh
pip install harborforge
```

Or with uv:
```sh
uv add harborforge
```

## Usage

Implement `DatasetHandler` for each dataset type in your benchmark, then `DataMapper` to iterate over tasks:

```python
from harborforge import DataMapper, DatasetHandler

class MyHandler(DatasetHandler):
    dataset_name = "my_dataset"

    def instruction(self, task_data):
        return f"Solve this: {task_data['problem']}"

    def dockerfile(self, task_data):
        return "FROM python:3.12-slim\nWORKDIR /app\n"

    def test_sh(self, task_data):
        answer = task_data["answer"]
        return f"""#!/bin/bash
mkdir -p /logs/verifier
actual=$(cat /output/answer.txt 2>/dev/null)
[ "$actual" = "{answer}" ] && echo 1 || echo 0 > /logs/verifier/reward.txt
"""

class MyMapper(DataMapper):
    def iter_tasks(self):
        for i, task in enumerate(load_my_benchmark()):
            yield f"my_dataset/{i}", f"my_dataset/{i}", MyHandler(), task

# Generate Harbor task directories
MyMapper().run(output_dir=Path(".data/tasks"), registry_path=Path("registry.json"))
```

## Handler contract

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

## Reference implementation

[g9](https://github.com/altaiiiir/g9) — maps [DSGym](https://github.com/DS-Gym/DS-Gym) benchmarks to Harbor using HarborForge.
