"""Local search via notmuch CLI wrapper.

This module wraps the notmuch command-line tool to search emails stored
in Maildir format. We use subprocess instead of Python bindings for
easier installation and maintenance.
"""

import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from .models import SearchResult


class NotmuchError(Exception):
    """Error from notmuch command."""

    pass


class NotmuchNotFoundError(NotmuchError):
    """notmuch binary not found."""

    pass


class NotmuchDatabaseError(NotmuchError):
    """notmuch database not initialized."""

    pass


def check_notmuch_available() -> None:
    """Check if notmuch is installed and database exists.

    Raises:
        NotmuchNotFoundError: If notmuch binary is not found.
        NotmuchDatabaseError: If notmuch database is not initialized.
    """
    if not shutil.which("notmuch"):
        raise NotmuchNotFoundError(
            "notmuch not found. Install with: apt install notmuch"
        )

    # Check if database exists (notmuch stores it in the mail root)
    # We check by running notmuch count which fails if no database
    result = subprocess.run(
        ["notmuch", "count", "*"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if "database" in result.stderr.lower() or "no mail" in result.stderr.lower():
            raise NotmuchDatabaseError("Run 'notmuch new' to index your mail")
        # Other error - might still be usable
        pass


def search_local(
    query: str,
    mail_dir: Path,
    account_name: str,
    limit: int = 50,
) -> list[SearchResult]:
    """Search local mail using notmuch.

    Args:
        query: notmuch query string (e.g., "from:alice@example.com")
        mail_dir: Path to account's mail directory (e.g., ~/Mail/Gmail-capcor)
        account_name: Account name for result attribution
        limit: Maximum number of results to return

    Returns:
        List of SearchResult objects matching the query.

    Raises:
        NotmuchNotFoundError: If notmuch is not installed.
        NotmuchDatabaseError: If notmuch database is not initialized.
        NotmuchError: For other notmuch errors (invalid query, etc).
    """
    check_notmuch_available()

    # Scope query to this account's folder
    # mail_dir might be ~/Maildir/capocor-gmail, we want path:capocor-gmail/**
    # The path: prefix matches messages under that directory tree
    folder_name = mail_dir.name
    scoped_query = f"path:{folder_name}/** AND ({query})"

    # Step 1: Get message IDs matching the query
    message_ids = _get_message_ids(scoped_query, limit)

    if not message_ids:
        return []

    # Step 2: Get full message data for each ID
    results = []
    for msg_id in message_ids:
        result = _get_message_data(msg_id, account_name)
        if result:
            results.append(result)

    return results


def _get_message_ids(query: str, limit: int) -> list[str]:
    """Get message IDs matching a query.

    Uses: notmuch search --format=json --output=messages --limit=N <query>
    """
    result = subprocess.run(
        [
            "notmuch",
            "search",
            "--format=json",
            "--output=messages",
            f"--limit={limit}",
            query,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise NotmuchError(result.stderr.strip() or "notmuch search failed")

    try:
        # Output is a JSON array of message IDs
        return json.loads(result.stdout) if result.stdout.strip() else []
    except json.JSONDecodeError as e:
        raise NotmuchError(f"Failed to parse notmuch output: {e}")


def _get_message_data(message_id: str, account_name: str) -> SearchResult | None:
    """Get full message data for a single message ID.

    Uses: notmuch show --format=json --body=true id:<message_id>
    """
    result = subprocess.run(
        [
            "notmuch",
            "show",
            "--format=json",
            "--body=true",
            f"id:{message_id}",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        # Skip messages we can't read
        return None

    try:
        data = json.loads(result.stdout)
        return _parse_message_json(data, account_name)
    except (json.JSONDecodeError, KeyError, IndexError):
        # Skip malformed messages
        return None


def _parse_message_json(data: list, account_name: str) -> SearchResult | None:
    """Parse notmuch show JSON output into a SearchResult.

    notmuch show returns a nested structure:
    [
      [
        [
          {"id": ..., "headers": {...}, "body": [...], ...},
          []  # replies
        ]
      ]
    ]
    """
    # Navigate the nested structure to get the message
    # Structure: list of threads -> list of messages -> (message, replies)
    if not data or not data[0] or not data[0][0]:
        return None

    message = data[0][0][0]  # First thread, first message pair, message itself

    headers = message.get("headers", {})
    body_parts = message.get("body", [])

    # Parse date
    date_str = headers.get("Date", "")
    try:
        # notmuch provides RFC 2822 format dates
        date = _parse_email_date(date_str)
    except ValueError:
        date = datetime.now()

    # Extract body snippet and attachments
    snippet, attachments = _extract_body_and_attachments(body_parts)

    # Parse To header (might be comma-separated list)
    to_header = headers.get("To", "")
    to_addrs = [addr.strip() for addr in to_header.split(",") if addr.strip()]

    # notmuch may return multiple filenames if message is in multiple folders
    # Use the first one (usually INBOX)
    filename = message.get("filename")
    if isinstance(filename, list):
        filename = filename[0] if filename else None

    return SearchResult(
        id=message.get("id", ""),
        account=account_name,
        file=filename,
        date=date,
        from_addr=headers.get("From", ""),
        to_addrs=to_addrs,
        subject=headers.get("Subject", ""),
        snippet=snippet,
        tags=message.get("tags", []),
        attachments=attachments,
    )


def _parse_email_date(date_str: str) -> datetime:
    """Parse RFC 2822 email date string.

    Examples:
        "Mon, 15 Jan 2024 10:00:00 +0000"
        "15 Jan 2024 10:00:00 -0500"
    """
    from email.utils import parsedate_to_datetime

    return parsedate_to_datetime(date_str)


def _extract_body_and_attachments(
    body_parts: list,
) -> tuple[str, list[str]]:
    """Extract body snippet and attachment filenames from message body.

    Walks through MIME parts to find text content and attachments.
    Returns a ~200 char snippet of the body text.
    """
    text_content = []
    attachments = []

    def walk_parts(parts: list) -> None:
        for part in parts:
            content_type = part.get("content-type", "")

            # Handle nested multipart
            if "content" in part and isinstance(part["content"], list):
                walk_parts(part["content"])
                continue

            # Check for attachment
            filename = part.get("filename")
            if filename:
                attachments.append(filename)
                continue

            # Extract text content
            if content_type.startswith("text/plain"):
                content = part.get("content", "")
                if isinstance(content, str):
                    text_content.append(content)
            elif content_type.startswith("text/html") and not text_content:
                # Use HTML only if no plain text available
                content = part.get("content", "")
                if isinstance(content, str):
                    text_content.append(_strip_html(content))

    walk_parts(body_parts)

    # Combine text and create snippet
    full_text = " ".join(text_content)
    snippet = _create_snippet(full_text, max_length=200)

    return snippet, attachments


def _strip_html(html: str) -> str:
    """Remove HTML tags from a string."""
    # Remove script and style content entirely
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.I)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.I)
    # Remove all remaining tags
    html = re.sub(r"<[^>]+>", " ", html)
    # Decode common HTML entities
    html = html.replace("&nbsp;", " ")
    html = html.replace("&amp;", "&")
    html = html.replace("&lt;", "<")
    html = html.replace("&gt;", ">")
    html = html.replace("&quot;", '"')
    return html


def _create_snippet(text: str, max_length: int = 200) -> str:
    """Create a text snippet, truncating at word boundary."""
    # Normalize whitespace
    text = " ".join(text.split())

    if len(text) <= max_length:
        return text

    # Truncate at word boundary
    truncated = text[:max_length]
    last_space = truncated.rfind(" ")
    if last_space > max_length // 2:
        truncated = truncated[:last_space]

    return truncated + "..."
