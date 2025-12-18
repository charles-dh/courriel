"""Read command implementation."""

import typer
from typing_extensions import Annotated

app = typer.Typer(help="Display email message(s)")


@app.callback(invoke_without_command=True)
def read(
    ctx: typer.Context,
    message_id: Annotated[str, typer.Argument(help="Message ID to read")],
    format: Annotated[str, typer.Option("--format", help="Output format: text, json, raw, headers")] = "text",
    no_attachments: Annotated[bool, typer.Option("--no-attachments", help="Don't show attachment info")] = False,
    save_attachments: Annotated[str | None, typer.Option("--save-attachments", help="Save attachments to directory")] = None,
):
    """Display email message(s)."""
    typer.echo("Read command - not yet implemented")
    typer.echo(f"  message_id: {message_id}")
    typer.echo(f"  format: {format}")
    typer.echo(f"  no_attachments: {no_attachments}")
    typer.echo(f"  save_attachments: {save_attachments}")
