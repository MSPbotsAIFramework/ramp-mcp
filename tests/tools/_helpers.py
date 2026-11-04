"""Shared harness for unit-testing one tools/<resource>.py module in isolation.

Each test builds a throwaway FastMCP instance registering only the module
under test, with client_factory() returning a fake api_client -- the SOP's
recommended "mock your API" approach (SS10), no network, no real Ramp calls.
"""

import json
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP


async def call_tool(register_fn: Callable[[Any, Any], None], client: Any, tool_name: str, arguments: dict) -> dict:
    mcp = FastMCP("test")
    register_fn(mcp, lambda: client)
    content, _structured = await mcp.call_tool(tool_name, arguments)
    text = content[0].text
    return json.loads(text)
