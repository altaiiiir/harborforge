"""
DatasetHandler contract.

Each dataset subclass must implement:
  - instruction(task_data)  → str   content for instruction.md (shown to the agent, no answer leakage)
  - test_sh(task_data)      → str   content for tests/test.sh (must write reward to /logs/verifier/reward.txt)
  - dockerfile(task_data)   → str   content for environment/Dockerfile

Optional overrides:
  - data_files(task_data)   → list[tuple[Path, str]]  (local_path, dest_in_build_context) pairs
  - task_toml(task_id)      → str   content for task.toml
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class DatasetHandler(ABC):
    dataset_name: str

    @abstractmethod
    def instruction(self, task_data: dict[str, Any]) -> str:
        """Returns instruction.md content — what the agent sees. Must not include the answer."""

    @abstractmethod
    def test_sh(self, task_data: dict[str, Any]) -> str:
        """Returns tests/test.sh content. Must write a float reward to /logs/verifier/reward.txt."""

    @abstractmethod
    def dockerfile(self, task_data: dict[str, Any]) -> str:
        """Returns environment/Dockerfile content."""

    def verifier_dockerfile(self, task_data: dict[str, Any]) -> str | None:
        """Return a Dockerfile for a SEPARATE verifier container, or None for SHARED (default).

        When non-None, Harbor routes the trial through SEPARATE mode: the verifier runs in
        its own isolated container and receives agent artifacts as input. Use this when the
        verifier needs different dependencies or ground truth data isolated from the agent.
        """
        return None

    def verifier_image_tag(self, task_data: dict[str, Any]) -> str | None:
        """Return a pre-built Docker image tag for the verifier base, or None to build from scratch.

        When non-None, tests/Dockerfile will use this as its FROM instead of the full
        verifier_dockerfile() content. The slow layers (e.g. pip installs) are pre-built
        into this image via `just build`, so per-trial builds only need to COPY test.sh.
        """
        return None

    def setup(self) -> None:
        """Download or prepare local data required by this dataset. No-op by default."""

    def artifacts(self) -> list[str]:
        """Container paths to capture as artifacts after a trial. Empty by default."""
        return []

    def verifier_env_keys(self) -> list[str]:
        """Environment variable keys to forward to the SEPARATE verifier container."""
        return []

    def data_files(self, task_data: dict[str, Any]) -> list[tuple[Path, str]]:
        """
        Returns (local_path, dest_in_build_context) pairs for files to COPY into the image.
        dest_in_build_context is relative to environment/ (e.g. 'data/train.csv').
        """
        return []

    def task_toml(self, task_id: str) -> str:
        return f"""\
version = "1.0"

[task]
name = "{task_id}"

[metadata]

[verifier]
timeout_sec = 900.0

[agent]
timeout_sec = 900.0

[environment]
build_timeout_sec = 600.0
"""


# ---------------------------------------------------------------------------
# Verifier shell script templates
# ---------------------------------------------------------------------------


def exact_match_verifier(answer: Any) -> str:
    """Reward 1.0 if agent output matches expected answer (whitespace-stripped string comparison)."""
    safe = str(answer).replace("'", "'\\''")
    return f"""\
#!/bin/bash
set -e
mkdir -p /logs/verifier

EXPECTED='{safe}'
SUBMISSION=/app/submission.txt

if [ ! -f "$SUBMISSION" ]; then
    echo "0" > /logs/verifier/reward.txt
    exit 0
fi

ACTUAL=$(cat "$SUBMISSION" | tr -d '[:space:]')
EXPECTED_CLEAN=$(echo "$EXPECTED" | tr -d '[:space:]')

if [ "$ACTUAL" = "$EXPECTED_CLEAN" ]; then
    echo "1" > /logs/verifier/reward.txt
else
    echo "0" > /logs/verifier/reward.txt
fi
"""


def numeric_verifier(answer: Any, tolerance: float = 0.05) -> str:
    """Reward 1.0 if agent output is within `tolerance` (relative) of expected numeric value."""
    safe = str(answer).replace("'", "'\\''")
    return f"""\
#!/bin/bash
set -e
mkdir -p /logs/verifier

EXPECTED='{safe}'

python3 - "$EXPECTED" <<'PYEOF'
import sys

try:
    expected = float(sys.argv[1])
    with open("/app/submission.txt") as f:
        actual = float(f.read().strip())
    denom = abs(expected) if expected != 0 else 1.0
    reward = 1.0 if abs(actual - expected) / denom <= {tolerance} else 0.0
except Exception:
    reward = 0.0

with open("/logs/verifier/reward.txt", "w") as f:
    f.write(str(reward))
PYEOF
"""


def list_verifier(answer: Any) -> str:
    """Reward 1.0 if agent output contains all expected items (order-insensitive, case-insensitive).
    Expected answer should be a Python list repr or comma-separated string."""
    safe = str(answer).replace("'", "'\\''")
    return f"""\
#!/bin/bash
set -e
mkdir -p /logs/verifier

python3 <<'PYEOF'
import ast, re

EXPECTED_RAW = '{safe}'
try:
    with open("/app/submission.txt") as f:
        actual_raw = f.read().strip()
except FileNotFoundError:
    open("/logs/verifier/reward.txt", "w").write("0")
    raise SystemExit

def parse_list(s):
    try:
        val = ast.literal_eval(s)
        if isinstance(val, list):
            return {{str(x).strip().lower() for x in val}}
    except Exception:
        pass
    return {{x.strip().lower() for x in re.split(r"[,\\n]+", s) if x.strip()}}

expected = parse_list(EXPECTED_RAW)
actual = parse_list(actual_raw)
reward = 1.0 if expected and expected == actual else 0.0
open("/logs/verifier/reward.txt", "w").write(str(reward))
PYEOF
"""


def case_insensitive_verifier(answer: Any) -> str:
    """Reward 1.0 if agent output matches expected answer, ignoring case and whitespace."""
    safe = str(answer).replace("'", "'\\''")
    return f"""\
#!/bin/bash
set -e
mkdir -p /logs/verifier

EXPECTED='{safe}'
SUBMISSION=/app/submission.txt

if [ ! -f "$SUBMISSION" ]; then
    echo "0" > /logs/verifier/reward.txt
    exit 0
fi

ACTUAL=$(cat "$SUBMISSION" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')
EXPECTED_CLEAN=$(echo "$EXPECTED" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')

if [ "$ACTUAL" = "$EXPECTED_CLEAN" ]; then
    echo "1" > /logs/verifier/reward.txt
else
    echo "0" > /logs/verifier/reward.txt
fi
"""


def script_verifier(script_container_path: str) -> str:
    """Runs a Python eval script already present in the container.
    The script is fully responsible for writing a float reward to /logs/verifier/reward.txt."""
    return f"""\
#!/bin/bash
set -e
mkdir -p /logs/verifier

SCRIPT="{script_container_path}"

if [ ! -f "$SCRIPT" ]; then
    echo "0" > /logs/verifier/reward.txt
    exit 0
fi

python3 "$SCRIPT" || echo "0" > /logs/verifier/reward.txt
"""


def no_verifier(reason: str = "External evaluation required") -> str:
    """Always writes reward 0. Used for tasks that require external scoring (e.g. leaderboards)."""
    return f"""\
#!/bin/bash
# {reason}
mkdir -p /logs/verifier
echo "0" > /logs/verifier/reward.txt
"""
