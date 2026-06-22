from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TaskEnrichment(Protocol):
    """
    Enriches a Harbor task at generation time.

    Implementations can inject additional instruction text and/or MCP server
    configs into each task directory without touching handler code.
    """

    def extra_instruction(self, task_data: dict[str, Any]) -> str | None:
        """Return markdown to append to instruction.md, or None to skip."""
        ...

    def mcp_servers(self, task_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Return list of MCP server dicts to add to task.toml (SSE/HTTP only)."""
        ...
