from __future__ import annotations

from chatbot.services.assistant import ChatbotService

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:
    raise RuntimeError("Install `mcp` package to run the MCP server.") from exc


service = ChatbotService()
mcp = FastMCP("customer-support-chatbot")


@mcp.tool()
def initialize_sql_data() -> str:
    """Initialize synthetic customer and support ticket data in SQLite."""
    return service.initialize_sql_data()


@mcp.tool()
def ingest_policy_pdfs(directory: str) -> str:
    """Ingest all PDF files from a directory into the vector database."""
    return service.ingest_policy_directory(directory)


@mcp.tool()
def ask_support_assistant(question: str) -> str:
    """Ask the multi-agent support chatbot a question."""
    return service.ask(question)


@mcp.tool()
def ask_support_assistant_with_route(question: str) -> str:
    """Ask the assistant and include selected route metadata."""
    result = service.ask_with_meta(question)
    return f"Route: {result['route']}\n\n{result['answer']}"


if __name__ == "__main__":
    mcp.run()
