"""List command implementation."""

import typer
from typing_extensions import Annotated
from enum import Enum

app = typer.Typer(help="List folders or messages")


class ListType(str, Enum):
    """Types of items to list."""
    folders = "folders"
    messages = "messages"


@app.callback(invoke_without_command=True)
def list_cmd(
    ctx: typer.Context,
    type: Annotated[ListType, typer.Argument(help="What to list: folders or messages")] = ListType.folders,
    remote: Annotated[bool, typer.Option("--remote", help="List from remote account")] = False,
    local: Annotated[bool, typer.Option("--local", help="List from local Maildir (default)")] = True,
    folder: Annotated[str | None, typer.Option("--folder", help="List messages in specific folder")] = None,
    max_messages: Annotated[int, typer.Option("--max-messages", help="Maximum number of messages to list")] = 50,
):
    """List folders or messages."""
    typer.echo("List command - not yet implemented")
    typer.echo(f"  type: {type}")
    typer.echo(f"  remote: {remote}, local: {local}")
    typer.echo(f"  folder: {folder}")
    typer.echo(f"  max_messages: {max_messages}")
