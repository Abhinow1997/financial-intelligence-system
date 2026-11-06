"""Step 2: the same notes server, now reachable over HTTP.

Three tools over a tiny DuckDB "notes" database. Still no auth.
Instead of being launched as a subprocess (stdio), it runs on its own and clients
connect to it over the network using MCP's streamable HTTP transport.
"""

from fastmcp import FastMCP

from notes_duckdb import add_note, delete_note, list_notes

mcp = FastMCP("notes")


@mcp.tool()
def list_my_notes() -> list[dict]:
    """List all saved notes."""
    return list_notes(owner="local")


@mcp.tool()
def add_a_note(text: str) -> dict:
    """Save a new note."""
    return add_note(owner="local", text=text)


@mcp.tool()
def delete_a_note(note_id: int) -> str:
    """Delete a note by id."""
    return "deleted" if delete_note(owner="local", note_id=note_id) else "not found"


if __name__ == "__main__":
    # Streamable HTTP: clients connect to http://localhost:8080/mcp
    mcp.run(transport="http", host="localhost", port=8080)
