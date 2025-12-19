"""Config command implementation.

Manages courriel configuration and Microsoft 365 authentication.
"""

import typer
from typing_extensions import Annotated

from courriel.auth import authenticate
from courriel.config import (
    CONFIG_FILE,
    get_account,
    init_config,
    load_config,
    set_config_value,
)
from courriel.config.paths import CONFIG_DIR
from courriel.config.schema import AccountConfig

app = typer.Typer(help="Manage configuration and authentication")


@app.command()
def init(
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite existing config")
    ] = False,
):
    """Initialize configuration directory and template config file."""
    created = init_config(overwrite=force)

    if created:
        typer.echo(f"Created config directory: {CONFIG_DIR}")
        typer.echo(f"Created config file: {CONFIG_FILE}")
        typer.echo()
        typer.echo("Edit the config file to add your account settings.")
    else:
        typer.echo(f"Config already exists at {CONFIG_FILE}")
        typer.echo("Use --force to overwrite.")


@app.command()
def auth(
    account: Annotated[
        str | None, typer.Option("--account", "-a", help="Account name to authenticate")
    ] = None,
):
    """Authenticate with Microsoft365 using Device Code Flow.

    Opens a browser for you to sign in with your Microsoft account.
    Tokens are cached locally for future use.
    """
    config = load_config()

    account_config = get_account(config, account)
    if not account_config:
        typer.echo("No account configured.", err=True)
        typer.echo()
        typer.echo("Run 'courriel config init' and add an account to config.toml")
        raise typer.Exit(1)

    typer.echo("Starting authentication...")
    typer.echo()

    result = authenticate(account_config)

    if "access_token" in result:
        # Extract username from token claims if available
        claims = result.get("id_token_claims", {})
        username = claims.get("preferred_username", claims.get("email", "Unknown"))

        typer.echo()
        typer.echo("Authentication successful!")
        typer.echo(f"Logged in as: {username}")
    else:
        typer.echo()
        error_msg = result.get(
            "error_description", result.get("error", "Unknown error")
        )
        typer.echo(f"Authentication failed: {error_msg}", err=True)
        raise typer.Exit(1)


@app.command()
def show(
    account: Annotated[
        str | None, typer.Option("--account", "-a", help="Show specific account")
    ] = None,
):
    """Display current configuration.

    Secrets (like client_secret) are redacted in output.
    """
    config = load_config()

    if not config:
        typer.echo("No configuration found.")
        typer.echo(f"Run 'courriel config init' to create {CONFIG_FILE}")
        return

    # Display defaults section
    if "defaults" in config:
        typer.echo("[defaults]")
        for key, value in config["defaults"].items():
            typer.echo(f"  {key} = {value}")
        typer.echo()

    # Display accounts
    accounts = config.get("accounts", {})

    if not accounts:
        typer.echo("No accounts configured.")
        return

    if account:
        # Show specific account
        if account in accounts:
            _display_account(account, accounts[account])
        else:
            typer.echo(f"Account '{account}' not found.", err=True)
            raise typer.Exit(1)
    else:
        # Show all accounts
        for name, acct in accounts.items():
            _display_account(name, acct)


def _display_account(name: str, account: AccountConfig) -> None:
    """Display a single account configuration with redacted secrets."""
    typer.echo(f"[accounts.{name}]")
    for key, value in account.items():
        if key == "client_secret":
            # Redact secret but indicate it's set
            display_value = "***REDACTED***" if value else "(not set)"
        else:
            display_value = value
        typer.echo(f"  {key} = {display_value}")
    typer.echo()


@app.command("set")
def set_value(
    key: Annotated[
        str,
        typer.Argument(
            help="Configuration key (dot notation, e.g., 'defaults.max_messages')"
        ),
    ],
    value: Annotated[str, typer.Argument(help="Configuration value")],
):
    """Set a configuration value using dot notation.

    Examples:
        courriel config set defaults.max_messages 200
        courriel config set accounts.work.tenant_id xxxx-xxxx
    """
    try:
        set_config_value(key, value)
        typer.echo(f"Set {key} = {value}")
    except ValueError as e:
        typer.echo(f"Invalid value: {e}", err=True)
        raise typer.Exit(1)
