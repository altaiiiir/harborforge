set shell := ["bash", "-c"]

default:
    @just --list

# Install dependencies (core + dev)
setup:
    uv sync --extra dev

# Run all tests
test:
    uv run pytest tests/ -v

# Format, auto-fix lint issues, and type-check
format:
    uv run ruff format .
    uv run ruff check . --fix
    uv run mypy harborforge/
