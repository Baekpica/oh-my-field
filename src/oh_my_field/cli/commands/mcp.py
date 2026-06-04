import typer

from oh_my_field.mcp.server import serve_stdio


def serve() -> None:
    serve_stdio()


def register(mcp_app: typer.Typer) -> None:
    mcp_app.command(
        "serve",
        help="Run the OMF MCP stdio server.",
    )(serve)
