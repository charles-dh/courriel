"""Main CLI entry point for courriel."""

import typer

from courriel import __version__
from courriel.cli import commands
from courriel.config import get_account_names, load_config
from courriel.config.paths import migrate_credential_files

app = typer.Typer(
    name="courriel",
    help="Personal email CLI tool for Microsoft365 and Gmail",
    no_args_is_help=True,
)

# Register command groups
app.add_typer(commands.sync.app, name="sync")
app.add_typer(commands.read.app, name="read")
app.add_typer(commands.draft.app, name="draft")
app.add_typer(commands.list.app, name="list")
app.add_typer(commands.config.app, name="config")

# Register search as a direct command (has a required argument)
app.command(name="search")(commands.search.search)


@app.callback()
def _startup() -> None:
    """Run once before any command.

    Handles one-time migrations (e.g. renaming legacy credential files
    to per-account names) so existing users aren't forced to re-authenticate.
    """
    config = load_config()
    names = get_account_names(config)
    if names:
        migrate_credential_files(names)


@app.command()
def version():
    """Show version information."""
    typer.echo(f"courriel version {__version__}")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
