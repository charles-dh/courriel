"""Draft command implementation."""

import typer
from typing_extensions import Annotated

app = typer.Typer(help="Create or reply to email drafts")


@app.callback(invoke_without_command=True)
def draft(
    ctx: typer.Context,
    to: Annotated[str | None, typer.Option("--to", help="Recipient(s)")] = None,
    cc: Annotated[str | None, typer.Option("--cc", help="CC recipient(s)")] = None,
    bcc: Annotated[str | None, typer.Option("--bcc", help="BCC recipient(s)")] = None,
    subject: Annotated[str | None, typer.Option("--subject", help="Email subject")] = None,
    body: Annotated[str | None, typer.Option("--body", help="Email body (or read from stdin)")] = None,
    reply_to: Annotated[str | None, typer.Option("--reply-to", help="Reply to message ID")] = None,
    attach: Annotated[list[str] | None, typer.Option("--attach", help="Attach file(s)")] = None,
):
    """Create or reply to email drafts."""
    typer.echo("Draft command - not yet implemented")
    typer.echo(f"  to: {to}")
    typer.echo(f"  cc: {cc}")
    typer.echo(f"  bcc: {bcc}")
    typer.echo(f"  subject: {subject}")
    typer.echo(f"  body: {body}")
    typer.echo(f"  reply_to: {reply_to}")
    typer.echo(f"  attach: {attach}")
