"""Sync command implementation."""

import typer
from typing_extensions import Annotated

app = typer.Typer(help="Synchronize emails between remote account and local Maildir")


@app.callback(invoke_without_command=True)
def sync(
    ctx: typer.Context,
    folder: Annotated[str | None, typer.Option(help="Sync specific folder")] = None,
    all: Annotated[bool, typer.Option("--all", help="Sync all folders")] = False,
    max_messages: Annotated[
        int | None, typer.Option(help="Maximum messages to sync per folder")
    ] = None,
    since: Annotated[
        str | None, typer.Option(help="Sync messages after date (YYYY-MM-DD)")
    ] = None,
    days: Annotated[
        int | None, typer.Option(help="Sync messages from last N days")
    ] = None,
):
    """Synchronize emails between remote account and local Maildir."""
    typer.echo("Sync command - not yet implemented")
    typer.echo(f"  folder: {folder}")
    typer.echo(f"  all: {all}")
    typer.echo(f"  max_messages: {max_messages}")
    typer.echo(f"  since: {since}")
    typer.echo(f"  days: {days}")
