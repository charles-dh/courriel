"""Sync command implementation.

Synchronizes emails from Gmail to local Maildir storage.
Supports both full and incremental sync modes.
"""

from datetime import date
from pathlib import Path

import typer
from typing_extensions import Annotated

from courriel.config import get_account, load_config
from courriel.sync.engine import SyncEngine, SyncResult
from courriel.sync.gmail import GmailClient, get_credentials
from courriel.sync.state import SyncState
from courriel.storage.maildir import MaildirStorage

app = typer.Typer(help="Synchronize emails between remote account and local Maildir")

# Default labels to sync when --all is specified
DEFAULT_LABELS = ["INBOX", "SENT", "DRAFT"]


def _parse_date(date_str: str) -> date:
    """Parse a YYYY-MM-DD date string.

    Args:
        date_str: Date in YYYY-MM-DD format.

    Returns:
        Parsed date object.

    Raises:
        typer.BadParameter: If date format is invalid.
    """
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise typer.BadParameter(
            f"Invalid date format: {date_str}. Expected YYYY-MM-DD."
        )


def _create_progress_callback() -> tuple[callable, dict]:
    """Create a progress callback and state tracker.

    Returns:
        Tuple of (callback function, state dict for tracking).
    """
    state = {"current_label": None, "shown_header": False}

    def progress_callback(label: str, current: int, total: int):
        # Print label header on first message
        if state["current_label"] != label:
            if state["shown_header"]:
                typer.echo()  # Newline after previous label
            state["current_label"] = label
            state["shown_header"] = True
            typer.echo(f"{label}:")

        # Print progress (overwrite line)
        typer.echo(f"  Syncing: {current}/{total} messages", nl=False)
        typer.echo("\r", nl=False)

        # Print final status on completion
        if current == total:
            typer.echo(f"  Syncing: {total}/{total} messages - done")

    return progress_callback, state


def _print_result(result: SyncResult) -> None:
    """Print sync result summary.

    Args:
        result: SyncResult from sync operation.
    """
    typer.echo()
    typer.echo("Sync complete:")
    typer.echo(f"  - {result.downloaded} messages downloaded")
    if result.skipped > 0:
        typer.echo(f"  - {result.skipped} already synced (skipped)")
    if result.errors > 0:
        typer.echo(f"  - {result.errors} errors")
        for detail in result.error_details[:5]:  # Show first 5 errors
            typer.echo(f"    - {detail}", err=True)
        if len(result.error_details) > 5:
            typer.echo(f"    ... and {len(result.error_details) - 5} more", err=True)


@app.callback(invoke_without_command=True)
def sync(
    ctx: typer.Context,
    folder: Annotated[
        str | None,
        typer.Option(help="Sync specific label (e.g., INBOX, SENT)"),
    ] = None,
    all_labels: Annotated[
        bool,
        typer.Option("--all", help="Sync all default labels (INBOX, SENT, DRAFT)"),
    ] = False,
    max_messages: Annotated[
        int | None,
        typer.Option(help="Maximum messages to sync per label (default: 100)"),
    ] = None,
    since: Annotated[
        str | None,
        typer.Option(help="Sync messages after date (YYYY-MM-DD)"),
    ] = None,
    days: Annotated[
        int | None,
        typer.Option(help="Sync messages from last N days"),
    ] = None,
    account: Annotated[
        str | None,
        typer.Option("--account", "-a", help="Account name to sync"),
    ] = None,
    full: Annotated[
        bool,
        typer.Option("--full", help="Force full sync (ignore incremental state)"),
    ] = False,
):
    """Synchronize emails from Gmail to local Maildir.

    Examples:

        # Sync inbox with default limits
        courriel sync --folder INBOX

        # Sync all default labels
        courriel sync --all

        # Sync inbox, last 30 days
        courriel sync --folder INBOX --days 30

        # Sync with custom message limit
        courriel sync --folder INBOX --max-messages 50

        # Force full sync (re-download all)
        courriel sync --all --full
    """
    # Validate options
    if not folder and not all_labels:
        typer.echo("Error: Must specify --folder or --all", err=True)
        typer.echo()
        typer.echo("Examples:")
        typer.echo("  courriel sync --folder INBOX")
        typer.echo("  courriel sync --all")
        raise typer.Exit(1)

    if since and days:
        typer.echo("Error: Cannot specify both --since and --days", err=True)
        raise typer.Exit(1)

    # Load configuration
    config = load_config()
    account_config = get_account(config, account)

    if not account_config:
        typer.echo("Error: No account configured.", err=True)
        typer.echo()
        typer.echo("Run 'courriel config init' and add an account to config.toml")
        raise typer.Exit(1)

    # Check provider
    provider = account_config.get("provider", "ms365")
    if provider != "gmail":
        typer.echo(
            f"Error: Provider '{provider}' not yet supported for sync.", err=True
        )
        typer.echo("Currently only Gmail is supported.")
        raise typer.Exit(1)

    # Get account name for state file and credential lookup
    account_name = account or next(iter(config.get("accounts", {}).keys()), "default")

    # Check authentication
    credentials = get_credentials(account_name)
    if not credentials or not credentials.valid:
        typer.echo("Error: Not authenticated.", err=True)
        typer.echo()
        typer.echo("Run 'courriel config auth' first to authenticate with Gmail.")
        raise typer.Exit(1)

    # Determine labels to sync
    if folder:
        labels = [folder]
    else:
        # Use defaults from config or fallback
        labels = config.get("defaults", {}).get("sync_labels", DEFAULT_LABELS)

    # Get settings with defaults
    defaults = config.get("defaults", {})
    msg_limit = max_messages or defaults.get("max_messages", 100)

    # Parse date filter
    since_date = _parse_date(since) if since else None

    # Get mail directory from config
    mail_dir = account_config.get("mail_dir", "~/Mail")
    mail_path = Path(mail_dir).expanduser()

    # Create engine components
    gmail_client = GmailClient(credentials)
    maildir = MaildirStorage(mail_path)
    state = SyncState(account_name)

    engine = SyncEngine(gmail_client, maildir, state)

    # Print sync info
    typer.echo(f"Syncing {account_name} account...")
    typer.echo(f"  Labels: {', '.join(labels)}")
    if since_date:
        typer.echo(f"  Since: {since_date}")
    elif days:
        typer.echo(f"  Last {days} days")
    typer.echo()

    # Create progress callback
    progress_callback, _ = _create_progress_callback()

    # Perform sync
    try:
        result = engine.sync(
            labels=labels,
            max_messages=msg_limit,
            since=since_date,
            days=days,
            progress_callback=progress_callback,
            force_full=full,
        )
    except Exception as e:
        typer.echo()
        typer.echo(f"Error during sync: {e}", err=True)
        raise typer.Exit(1)

    # Print result
    _print_result(result)

    # Exit with error code if there were errors
    if result.errors > 0:
        raise typer.Exit(1)
