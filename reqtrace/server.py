"""ReqTrace MCP server (stdio, FastMCP).

Thin transport wrapper around :mod:`reqtrace.logic` — all behaviour lives
there and is tested without MCP. All tools are read-only.

The database path comes from the ``REQTRACE_DB`` environment variable and
defaults to ``reqtrace.db`` in the project root. Build it first with
``python -m reqtrace.build_db``.
"""
from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import logic

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("REQTRACE_DB", str(PROJECT_ROOT / "reqtrace.db"))

mcp = FastMCP("reqtrace")


@mcp.tool()
def list_requirements(subsystem: str | None = None,
                      priority: str | None = None) -> list[dict]:
    """List requirements, optionally filtered by subsystem (full name or
    code such as NAV) and/or priority (Critical, High, Medium, Low)."""
    return logic.list_requirements(DB_PATH, subsystem=subsystem,
                                   priority=priority)


@mcp.tool()
def get_requirement(req_id: str) -> dict:
    """Get one requirement (e.g. REQ-NAV-001) with its linked tests and
    each test's latest result."""
    result = logic.get_requirement(DB_PATH, req_id)
    if result is None:
        return {"error": f"Requirement {req_id} not found"}
    return result


@mcp.tool()
def search_requirements(query: str) -> list[dict]:
    """Search requirements by keyword across id, title, and text."""
    return logic.search_requirements(DB_PATH, query)


@mcp.tool()
def find_uncovered_requirements() -> list[dict]:
    """Requirements with no linked test, or no passing latest test result."""
    return logic.find_uncovered_requirements(DB_PATH)


@mcp.tool()
def get_failing_tests() -> list[dict]:
    """Tests whose latest result is fail or blocked, with linked
    requirements."""
    return logic.get_failing_tests(DB_PATH)


@mcp.tool()
def get_coverage_summary() -> dict:
    """Verification coverage counts and percentages, overall and by
    subsystem."""
    return logic.get_coverage_summary(DB_PATH)


@mcp.tool()
def generate_qualification_report() -> str:
    """Generate a Markdown qualification report: coverage by subsystem,
    uncovered requirements, failing tests, and overall status."""
    return logic.generate_qualification_report(DB_PATH)


if __name__ == "__main__":
    mcp.run()  # stdio transport by default
