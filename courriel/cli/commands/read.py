"""Read command implementation.

Reads and displays a single email message from a Maildir file path.
Designed for the search-then-read workflow:
    courriel search "from:alice" --output files | head -1 | xargs courriel read

Usage:
    courriel read /path/to/maildir/message
    courriel read /path/to/message --output json
    courriel read /path/to/message --output raw
    courriel read /path/to/message --output headers
"""

import json
from pathlib import Path

import typer
from typing_extensions import Annotated

from courriel.read import read_message

app = typer.Typer(help="Display email message(s)")


@app.callback(invoke_without_command=True)
def read(
    ctx: typer.Context,
    file_path: Annotated[
        str,
        typer.Argument(help="Path to a Maildir message file"),
    ],
    output: Annotated[
        str,
        typer.Option("--output", help="Output format: text, json, raw, headers"),
    ] = "text",
) -> None:
    """Read and display a single email message from a Maildir file."""
    # Validate output format
    valid_formats = ("text", "json", "raw", "headers")
    if output not in valid_formats:
        typer.echo(f"Error: Invalid output format '{output}'", err=True)
        typer.echo(f"Valid formats: {', '.join(valid_formats)}", err=True)
        raise typer.Exit(1)

    path = Path(file_path).expanduser()

    if not path.exists():
        typer.echo(f"Error: File not found: {file_path}", err=True)
        raise typer.Exit(1)

    if not path.is_file():
        typer.echo(f"Error: Not a file: {file_path}", err=True)
        raise typer.Exit(1)

    # Raw mode: just dump the file contents, no parsing
    if output == "raw":
        typer.echo(path.read_text(errors="replace"), nl=False)
        return

    # Parse the email
    try:
        msg = read_message(path)
    except Exception as e:
        typer.echo(f"Error: Could not parse email: {e}", err=True)
        raise typer.Exit(1)

    if output == "json":
        _output_json(msg)
    elif output == "headers":
        _output_headers(msg)
    else:
        _output_text(msg)


def _output_json(msg) -> None:
    """Output message as JSON."""
    typer.echo(json.dumps(msg.to_dict(), indent=2))


def _output_headers(msg) -> None:
    """Output only the message headers."""
    typer.echo(f"File: {msg.file}")
    typer.echo(f"Date: {msg.date.isoformat()}")
    typer.echo(f"From: {msg.from_addr}")
    if msg.to_addrs:
        typer.echo(f"To: {', '.join(msg.to_addrs)}")
    if msg.cc_addrs:
        typer.echo(f"Cc: {', '.join(msg.cc_addrs)}")
    if msg.bcc_addrs:
        typer.echo(f"Bcc: {', '.join(msg.bcc_addrs)}")
    typer.echo(f"Subject: {msg.subject}")
    typer.echo(f"Message-ID: {msg.message_id}")
    if msg.in_reply_to:
        typer.echo(f"In-Reply-To: {msg.in_reply_to}")
    if msg.attachments:
        typer.echo(f"Attachments: {len(msg.attachments)}")
        for att in msg.attachments:
            typer.echo(
                f"  - {att['filename']} ({att['content_type']}, {att['size']} bytes)"
            )


def _output_text(msg) -> None:
    """Output message in human-readable text format."""
    # Header block
    typer.echo(f"From: {msg.from_addr}")
    if msg.to_addrs:
        typer.echo(f"To: {', '.join(msg.to_addrs)}")
    if msg.cc_addrs:
        typer.echo(f"Cc: {', '.join(msg.cc_addrs)}")
    typer.echo(f"Date: {msg.date.isoformat()}")
    typer.echo(f"Subject: {msg.subject}")
    typer.echo()  # Blank line separating headers from body

    # Body — prefer plain text, fall back to HTML
    if msg.body_plain:
        typer.echo(msg.body_plain)
    elif msg.body_html:
        # Strip HTML tags for readable text output
        typer.echo(_strip_html(msg.body_html))
    else:
        typer.echo("(no body)")

    # Attachment summary
    if msg.attachments:
        typer.echo()
        typer.echo(f"Attachments ({len(msg.attachments)}):")
        for att in msg.attachments:
            typer.echo(
                f"  - {att['filename']} ({att['content_type']}, {att['size']} bytes)"
            )


def _strip_html(html: str) -> str:
    """Crude HTML tag stripping for text output.

    Not a full HTML parser — just removes tags and collapses whitespace.
    Good enough for displaying HTML-only emails as readable text.
    """
    import re

    # Remove style and script blocks entirely
    text = re.sub(
        r"<(style|script)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE
    )
    # Replace <br> and block-level tags with newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|tr|li|h[1-6])>", "\n", text, flags=re.IGNORECASE)
    # Remove remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
