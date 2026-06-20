"""Unit tests for harborforge.handlers.base — verifier templates and DatasetHandler contract."""

import tomllib
from typing import Any

from harborforge.handlers.base import (
    DatasetHandler,
    case_insensitive_verifier,
    exact_match_verifier,
    list_verifier,
    no_verifier,
    numeric_verifier,
    script_verifier,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _StubHandler(DatasetHandler):
    """Minimal concrete handler for testing the base contract."""

    dataset_name = "stub"

    def instruction(self, task_data: dict[str, Any]) -> str:
        return task_data.get("question", "")

    def test_sh(self, task_data: dict[str, Any]) -> str:
        return exact_match_verifier(task_data.get("answer", ""))

    def dockerfile(self, task_data: dict[str, Any]) -> str:
        return "FROM python:3.11-slim\n\nWORKDIR /app\n"


# ---------------------------------------------------------------------------
# exact_match_verifier
# ---------------------------------------------------------------------------


class TestExactMatchVerifier:
    def test_contains_expected_value(self):
        script = exact_match_verifier("42")
        assert "EXPECTED='42'" in script

    def test_writes_reward_file(self):
        script = exact_match_verifier("x")
        assert "/logs/verifier/reward.txt" in script

    def test_checks_submission_file(self):
        script = exact_match_verifier("x")
        assert "/app/submission.txt" in script

    def test_missing_submission_gives_zero(self):
        script = exact_match_verifier("x")
        assert 'echo "0" > /logs/verifier/reward.txt' in script

    def test_escapes_single_quotes(self):
        script = exact_match_verifier("it's fine")
        # Shell-safe escaping: close quote, literal ', reopen quote — i.e. '\''
        assert "'\\''" in script
        assert "EXPECTED=" in script

    def test_numeric_answer(self):
        script = exact_match_verifier(3.14)
        assert "3.14" in script

    def test_none_answer(self):
        script = exact_match_verifier(None)
        assert "EXPECTED='None'" in script


# ---------------------------------------------------------------------------
# numeric_verifier
# ---------------------------------------------------------------------------


class TestNumericVerifier:
    def test_contains_expected_value(self):
        script = numeric_verifier("3.14")
        assert "3.14" in script

    def test_uses_python3(self):
        script = numeric_verifier("1.0")
        assert "python3" in script

    def test_default_tolerance(self):
        script = numeric_verifier("1.0")
        assert "0.05" in script

    def test_custom_tolerance(self):
        script = numeric_verifier("1.0", tolerance=0.01)
        assert "0.01" in script

    def test_writes_reward_file(self):
        script = numeric_verifier("1.0")
        assert "/logs/verifier/reward.txt" in script

    def test_handles_zero_denominator(self):
        script = numeric_verifier("0")
        assert "denom" in script  # should have a zero-safe denominator


# ---------------------------------------------------------------------------
# no_verifier
# ---------------------------------------------------------------------------


class TestNoVerifier:
    def test_always_writes_zero(self):
        script = no_verifier()
        assert 'echo "0"' in script

    def test_includes_reason_as_comment(self):
        script = no_verifier("needs leaderboard")
        assert "needs leaderboard" in script

    def test_default_reason(self):
        script = no_verifier()
        assert "External evaluation" in script


# ---------------------------------------------------------------------------
# list_verifier
# ---------------------------------------------------------------------------


class TestListVerifier:
    def test_writes_reward_file(self):
        script = list_verifier("['A', 'B']")
        assert "/logs/verifier/reward.txt" in script

    def test_uses_python3(self):
        script = list_verifier("['A', 'B']")
        assert "python3" in script

    def test_contains_expected_value(self):
        script = list_verifier("['PTPRC', 'CD8A']")
        assert "PTPRC" in script

    def test_handles_python_list_repr(self):
        # Answer stored as Python list repr — verifier must parse it
        script = list_verifier("['GENE1', 'GENE2', 'GENE3']")
        assert "ast.literal_eval" in script

    def test_handles_empty_answer(self):
        script = list_verifier("")
        assert "/logs/verifier/reward.txt" in script

    def test_handles_numeric_list(self):
        script = list_verifier("[1, 2, 3]")
        assert "1" in script

    def test_missing_submission_gives_zero(self):
        script = list_verifier("['A']")
        assert '"0"' in script or "'0'" in script


# ---------------------------------------------------------------------------
# case_insensitive_verifier
# ---------------------------------------------------------------------------


class TestCaseInsensitiveVerifier:
    def test_writes_reward_file(self):
        script = case_insensitive_verifier("19th century")
        assert "/logs/verifier/reward.txt" in script

    def test_contains_expected_value(self):
        script = case_insensitive_verifier("19th century")
        assert "19th century" in script

    def test_lowercases_both_sides(self):
        script = case_insensitive_verifier("Answer")
        assert "[:lower:]" in script

    def test_strips_whitespace(self):
        script = case_insensitive_verifier("foo bar")
        assert "[:space:]" in script

    def test_missing_submission_gives_zero(self):
        script = case_insensitive_verifier("x")
        assert 'echo "0" > /logs/verifier/reward.txt' in script

    def test_numeric_answer(self):
        script = case_insensitive_verifier(42)
        assert "42" in script


# ---------------------------------------------------------------------------
# script_verifier
# ---------------------------------------------------------------------------


class TestScriptVerifier:
    def test_writes_reward_file(self):
        script = script_verifier("/eval/my_eval.py")
        assert "/logs/verifier/reward.txt" in script

    def test_runs_python3(self):
        script = script_verifier("/eval/my_eval.py")
        assert "python3" in script

    def test_script_path_injected(self):
        script = script_verifier("/eval/my_eval.py")
        assert "/eval/my_eval.py" in script

    def test_missing_script_gives_zero(self):
        script = script_verifier("/eval/my_eval.py")
        assert "echo" in script and '"0"' in script

    def test_different_paths(self):
        script = script_verifier("/data/scienceagentbench/eval_programs/clintox_nn_eval.py")
        assert "clintox_nn_eval.py" in script


# ---------------------------------------------------------------------------
# DatasetHandler base contract
# ---------------------------------------------------------------------------


class TestDatasetHandlerContract:
    def test_task_toml_is_valid_toml(self):
        handler = _StubHandler()
        toml_str = handler.task_toml("myorg/task-1")
        parsed = tomllib.loads(toml_str)
        assert "verifier" in parsed
        assert "agent" in parsed
        assert "environment" in parsed

    def test_task_toml_contains_task_id(self):
        handler = _StubHandler()
        toml_str = handler.task_toml("myorg/task-1")
        assert "myorg/task-1" in toml_str

    def test_data_files_default_empty(self):
        handler = _StubHandler()
        assert handler.data_files({}) == []

    def test_instruction_does_not_contain_answer(self):
        handler = _StubHandler()
        task = {"question": "What is 2+2?", "answer": "4"}
        instruction = handler.instruction(task)
        assert "4" not in instruction
        assert "What is 2+2?" in instruction

    def test_setup_is_noop_by_default(self):
        handler = _StubHandler()
        handler.setup()  # must not raise

    def test_artifacts_empty_by_default(self):
        assert _StubHandler().artifacts() == []

    def test_verifier_env_keys_empty_by_default(self):
        assert _StubHandler().verifier_env_keys() == []
