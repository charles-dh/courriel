"""Main CLI entry point for courriel."""

import typer
from typing_extensions import Annotated

from courriel import __version__
from courriel.cli import commands

app = typer.Typer(
    name="courriel",
    help="Personal email CLI tool for Microsoft365 and Gmail",
    no_args_is_help=True,
)

# Register command groups
app.add_typer(commands.sync.app, name="sync")
app.add_typer(commands.search.app, name="search")
app.add_typer(commands.read.app, name="read")
app.add_typer(commands.draft.app, name="draft")
app.add_typer(commands.list.app, name="list")
app.add_typer(commands.config.app, name="config")


@app.command()
def version():
    """Show version information."""
    typer.echo(f"courriel version {__version__}")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
