"""Turns the tools on our MCP server into LangChain tools the agent can call.

Why not use the langchain-mcp-adapters package? Its current releases require
mcp<2, while FastMCP 4 is built on mcp 2.x, so the two can't be installed
together. FastMCP has its own MCP client, so this small adapter does the same job:

1. Connect to the MCP server and list its tools (name, description, input schema).
2. Wrap each one in a LangChain StructuredTool whose coroutine calls the MCP tool.
"""
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from langchain_core.tools import StructuredTool, ToolException
from mcp.types import Tool as McpTool

COMPANY_HEADER = "x-company-id"


def _mcp_client(url: str, company_id: int) -> Client:
    # The company id travels as an HTTP header set by our code, never by the LLM.
    transport = StreamableHttpTransport(url, headers={COMPANY_HEADER: str(company_id)})
    return Client(transport)


def _to_langchain_tool(mcp_tool: McpTool, url: str, company_id: int) -> StructuredTool:
    async def call_mcp_tool(**arguments) -> str:
        # A fresh MCP session per call: simple, and fast enough on localhost.
        async with _mcp_client(url, company_id) as client:
            result = await client.call_tool(mcp_tool.name, arguments, raise_on_error=False)

        text = "\n".join(block.text for block in result.content if hasattr(block, "text"))
        if result.is_error:
            # With handle_tool_error=True below, LangChain turns this into a normal tool
            # result, so the LLM reads the message (e.g. "invalid phone number") and recovers.
            raise ToolException(text)
        return text

    return StructuredTool(
        name=mcp_tool.name,
        description=mcp_tool.description or "",
        args_schema=mcp_tool.input_schema,  # the JSON schema FastMCP built from our type hints
        coroutine=call_mcp_tool,
        handle_tool_error=True,
    )


async def load_mcp_tools(url: str, company_id: int) -> list[StructuredTool]:
    """Fetch the tool list from the MCP server and wrap each tool for LangChain."""
    async with _mcp_client(url, company_id) as client:
        mcp_tools = await client.list_tools()
    return [_to_langchain_tool(tool, url, company_id) for tool in mcp_tools]