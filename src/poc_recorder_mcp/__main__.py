"""CLI entrypoint for the PoC Recorder MCP stdio server."""

from __future__ import annotations

import logging
import os
import sys

import anyio
from mcp.server.stdio import stdio_server

from poc_recorder_mcp.server import create_server


def configure_logging() -> None:
    """Structured key=value logging to stderr (stdout is reserved for the MCP stdio transport)."""
    level_name = os.environ.get("POC_RECORDER_MCP_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s level=%(levelname)s logger=%(name)s %(message)s"))
    root = logging.getLogger("poc_recorder_mcp")
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(handler)
    root.propagate = False


async def async_main() -> None:
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    configure_logging()
    anyio.run(async_main)


if __name__ == "__main__":
    main()
