#!/usr/bin/env python3
"""ReqTrace demo — no LLM, no API key, no cost.

Starts the MCP server over stdio, connects with the official MCP client
SDK, lists the tools, calls ``get_coverage_summary``, and prints the
qualification report produced by ``generate_qualification_report``.

This exercises the exact transport and protocol an AI agent (Claude Code,
Claude Desktop, or any MCP client) uses — only the question-asker is a
script instead of a model.

Usage:  .venv/bin/python demo.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "reqtrace.db"


def _text(result) -> str:
    return "".join(getattr(c, "text", "") for c in result.content)


async def main() -> None:
    if not DB_PATH.exists():
        from reqtrace import db as dbmod
        dbmod.build_from_seed(PROJECT_ROOT / "data" / "seed.json", DB_PATH)
        print(f"(built {DB_PATH.name} from seed data)\n")

    env = dict(os.environ, REQTRACE_DB=str(DB_PATH),
               PYTHONPATH=str(PROJECT_ROOT))
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "reqtrace.server"], env=env)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("Tools exposed by the ReqTrace MCP server:")
            for t in tools.tools:
                print(f"  - {t.name}")
            print()

            result = await session.call_tool("get_coverage_summary", {})
            if result.structuredContent:
                summary = result.structuredContent
            else:
                summary = json.loads(_text(result))
            print(f"Coverage: {summary['verified']} of "
                  f"{summary['total_requirements']} requirements verified "
                  f"({summary['coverage_pct']}%), "
                  f"{summary['unverified']} uncovered, "
                  f"{summary['failing_or_blocked_tests']} tests failing/blocked.\n")

            report = await session.call_tool("generate_qualification_report", {})
            print(_text(report))


if __name__ == "__main__":
    asyncio.run(main())
