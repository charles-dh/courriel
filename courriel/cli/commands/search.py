"""Search command implementation."""

import typer
from typing_extensions import Annotated

app = typer.Typer(help="Search emails locally or remotely")


@app.callback(invoke_without_command=True)
def search(
    ctx: typer.Context,
    query: Annotated[str | None, typer.Argument(help="Search query")] = None,
    local: Annotated[
        bool, typer.Option("--local", help="Search local Maildir (default)")
    ] = True,
    remote: Annotated[
        bool, typer.Option("--remote", help="Search remote account via API")
    ] = False,
    from_: Annotated[
        str | None, typer.Option("--from", help="Filter by sender")
    ] = None,
    to: Annotated[str | None, typer.Option("--to", help="Filter by recipient")] = None,
    subject: Annotated[
        str | None, typer.Option("--subject", help="Filter by subject")
    ] = None,
    body: Annotated[
        str | None, typer.Option("--body", help="Search in email body")
    ] = None,
    folder: Annotated[
        str | None, typer.Option("--folder", help="Limit to specific folder")
    ] = None,
    since: Annotated[
        str | None, typer.Option("--since", help="Start date (YYYY-MM-DD)")
    ] = None,
    until: Annotated[
        str | None, typer.Option("--until", help="End date (YYYY-MM-DD)")
    ] = None,
    format: Annotated[
        str, typer.Option("--format", help="Output format: summary, json, ids")
    ] = "summary",
):
    """Search emails locally or remotely."""
    typer.echo("Search command - not yet implemented")
    typer.echo(f"  query: {query}")
    typer.echo(f"  local: {local}, remote: {remote}")
    typer.echo(f"  from: {from_}, to: {to}")
    typer.echo(f"  subject: {subject}, body: {body}")
    typer.echo(f"  folder: {folder}")
    typer.echo(f"  since: {since}, until: {until}")
    typer.echo(f"  format: {format}")
