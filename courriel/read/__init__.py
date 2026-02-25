"""Email message reading and parsing.

Parses RFC 2822 email files from Maildir storage into structured
EmailMessage objects. Uses Python's email.parser module directly —
no notmuch dependency needed for reading.
"""

from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path

from courriel.read.models import EmailMessage

__all__ = ["EmailMessage", "read_message"]


def read_message(path: Path) -> EmailMessage:
    """Parse a Maildir email file into an EmailMessage.

    Args:
        path: Path to the RFC 2822 email file.

    Returns:
        EmailMessage with parsed headers, body, and attachment metadata.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the file can't be parsed as an email.
    """
    raw_bytes = path.read_bytes()

    # BytesParser with the default (compat32) policy handles
    # real-world malformed emails better than the "email" policy.
    parser = BytesParser(policy=policy.compat32)
    msg = parser.parsebytes(raw_bytes)

    # Parse date — fall back to epoch if missing/malformed
    date = _parse_date(msg.get("Date", ""))

    # Walk MIME parts to extract bodies and attachment metadata
    body_plain = None
    body_html = None
    attachments: list[dict] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))

            # Skip multipart containers themselves
            if part.get_content_maintype() == "multipart":
                continue

            # Attachments have a Content-Disposition of "attachment",
            # or an explicit filename on an inline part that isn't text
            if "attachment" in disposition or (
                part.get_filename() and content_type not in ("text/plain", "text/html")
            ):
                payload = part.get_payload(decode=True)
                attachments.append(
                    {
                        "filename": part.get_filename() or "unnamed",
                        "content_type": content_type,
                        "size": len(payload) if payload else 0,
                    }
                )
            elif content_type == "text/plain" and body_plain is None:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body_plain = payload.decode(charset, errors="replace")
            elif content_type == "text/html" and body_html is None:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body_html = payload.decode(charset, errors="replace")
    else:
        # Single-part message
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if content_type == "text/html":
                body_html = text
            else:
                body_plain = text

    return EmailMessage(
        file=str(path),
        date=date,
        from_addr=msg.get("From", ""),
        to_addrs=_parse_address_list(msg.get("To", "")),
        cc_addrs=_parse_address_list(msg.get("Cc", "")),
        bcc_addrs=_parse_address_list(msg.get("Bcc", "")),
        subject=msg.get("Subject", ""),
        message_id=msg.get("Message-ID", ""),
        in_reply_to=msg.get("In-Reply-To"),
        body_plain=body_plain,
        body_html=body_html,
        attachments=attachments,
    )


def _parse_date(date_str: str) -> datetime:
    """Parse an RFC 2822 date string, falling back to epoch on failure."""
    if not date_str:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    try:
        return parsedate_to_datetime(date_str)
    except (ValueError, TypeError):
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _parse_address_list(header: str) -> list[str]:
    """Split a comma-separated address header into individual addresses.

    Keeps the full "Name <email>" format for each address.
    Returns an empty list for empty/missing headers.
    """
    if not header:
        return []
    # Split on commas, but respect quoted strings and angle brackets
    return [addr.strip() for addr in header.split(",") if addr.strip()]
