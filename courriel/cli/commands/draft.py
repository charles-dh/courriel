"""Draft command implementation.

Creates Gmail drafts server-side via the Gmail API. Drafts appear
automatically in Gmail web and mobile clients (e.g. Spark).
"""

import sys
from pathlib import Path

import typer
from typing_extensions import Annotated

from courriel.config import get_account, load_config
from courriel.draft import build_draft_message, create_draft
from courriel.read import read_message
from courriel.sync.gmail import GmailClient, get_credentials

app = typer.Typer(help="Create or reply to email drafts")


@app.callback(invoke_without_command=True)
def draft(
    ctx: typer.Context,
    to: Annotated[str | None, typer.Option("--to", help="Recipient(s), comma-separated")] = None,
    cc: Annotated[str | None, typer.Option("--cc", help="CC recipient(s), comma-separated")] = None,
    bcc: Annotated[str | None, typer.Option("--bcc", help="BCC recipient(s), comma-separated")] = None,
    subject: Annotated[
        str | None, typer.Option("--subject", help="Email subject")
    ] = None,
    body: Annotated[
        str | None, typer.Option("--body", help="Email body (or pipe from stdin)")
    ] = None,
    reply_to: Annotated[
        str | None, typer.Option("--reply-to", help="Path to message file to reply to")
    ] = None,
    attach: Annotated[
        list[str] | None, typer.Option("--attach", help="File(s) to attach")
    ] = None,
    account: Annotated[
        str | None, typer.Option("--account", "-a", help="Account name to use")
    ] = None,
):
    """Create a Gmail draft (new message or reply).

    Examples:

        # New draft
        courriel draft --to alice@example.com --subject "Hello" --body "Hi there"

        # Reply to a local message file
        FILE=$(courriel search "from:alice" --output files --limit 1)
        courriel draft --reply-to "$FILE" --body "Thanks!"

        # Pipe body from stdin
        echo "Hello" | courriel draft --to alice@example.com --subject "Test"

        # With attachment
        courriel draft --to alice@example.com --subject "Report" --attach report.pdf
    """
    # Read body from stdin if --body not provided and stdin is a pipe
    if body is None and not sys.stdin.isatty():
        body = sys.stdin.read()

    # Load original message if --reply-to is provided
    original = None
    if reply_to:
        try:
            original = read_message(Path(reply_to))
        except FileNotFoundError:
            typer.echo(f"Error: File not found: {reply_to}", err=True)
            raise typer.Exit(1)
        except Exception as e:
            typer.echo(f"Error reading message: {e}", err=True)
            raise typer.Exit(1)

    # Resolve To and Subject with reply fallbacks
    resolved_to_str = to or (original.from_addr if original else None)
    resolved_subject = subject
    if resolved_subject is None and original:
        # Prepend "Re: " only if not already present
        orig_subject = original.subject or ""
        if orig_subject.lower().startswith("re:"):
            resolved_subject = orig_subject
        else:
            resolved_subject = f"Re: {orig_subject}"

    # Validate required fields
    if not resolved_to_str:
        typer.echo("Error: --to is required for new drafts", err=True)
        raise typer.Exit(1)
    if not resolved_subject:
        typer.echo("Error: --subject is required for new drafts", err=True)
        raise typer.Exit(1)
    if not body:
        typer.echo("Error: --body is required (or pipe from stdin)", err=True)
        raise typer.Exit(1)

    # Parse comma-separated address lists
    # Note: this breaks on display names containing commas (e.g. "Smith, J <j@x.com>")
    resolved_to = [addr.strip() for addr in resolved_to_str.split(",") if addr.strip()]
    resolved_cc = [addr.strip() for addr in cc.split(",") if addr.strip()] if cc else None
    resolved_bcc = [addr.strip() for addr in bcc.split(",") if addr.strip()] if bcc else None
    attach_paths = [Path(p) for p in attach] if attach else None

    # Load config and credentials
    config = load_config()
    account_config = get_account(config, account)

    if not account_config:
        typer.echo("Error: No account configured.", err=True)
        typer.echo()
        typer.echo("Run 'courriel config init' and add an account to config.toml")
        raise typer.Exit(1)

    provider = account_config.get("provider", "ms365")
    if provider != "gmail":
        typer.echo(f"Error: Provider '{provider}' not yet supported for drafts.", err=True)
        typer.echo("Currently only Gmail is supported.")
        raise typer.Exit(1)

    account_name = account or next(iter(config.get("accounts", {}).keys()), "default")
    credentials = get_credentials(account_name)
    if not credentials or not credentials.valid:
        typer.echo("Error: Not authenticated.", err=True)
        typer.echo()
        typer.echo("Run 'courriel config auth' first to authenticate with Gmail.")
        raise typer.Exit(1)

    # Build MIME message and create the draft
    mime_message = build_draft_message(
        to=resolved_to,
        subject=resolved_subject,
        body=body,
        cc=resolved_cc,
        bcc=resolved_bcc,
        reply_to_message=original,
        attach_paths=attach_paths,
    )

    client = GmailClient(credentials)
    draft_id = create_draft(client, mime_message)

    typer.echo(f"Draft created: {draft_id}")
