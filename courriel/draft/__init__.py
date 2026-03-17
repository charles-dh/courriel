"""Email drafting module.

Builds MIME messages and creates Gmail drafts via the API.
"""

import mimetypes
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from courriel.read.models import EmailMessage
from courriel.sync.gmail import GmailClient

__all__ = ["build_draft_message", "create_draft"]


def build_draft_message(
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    reply_to_message: EmailMessage | None = None,
    attach_paths: list[Path] | None = None,
) -> MIMEText | MIMEMultipart:
    """Build a MIME message from the given inputs.

    Pure function — no API calls. Returns a MIME object ready for
    base64url encoding and submission to the Gmail drafts API.

    Args:
        to: Recipient addresses (full "Name <email>" format is fine).
        subject: Email subject line.
        body: Plain-text body.
        cc: Optional CC addresses.
        bcc: Optional BCC addresses.
        reply_to_message: If replying, the original EmailMessage. Sets
            In-Reply-To and References threading headers.
        attach_paths: Optional list of file paths to attach.

    Returns:
        MIMEText for simple messages, MIMEMultipart when attachments are present.
    """
    if attach_paths:
        # Multipart message: text body + attachments
        msg = MIMEMultipart("mixed")
        msg.attach(MIMEText(body, "plain"))

        for path in attach_paths:
            # Guess MIME type from file extension; fall back to octet-stream
            mime_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            maintype, subtype = mime_type.split("/", 1)

            part = MIMEBase(maintype, subtype)
            part.set_payload(path.read_bytes())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                "attachment",
                filename=path.name,
            )
            msg.attach(part)
    else:
        msg = MIMEText(body, "plain")

    # Note: address parsing here uses a simple comma split which breaks on
    # display names containing commas (e.g. "Smith, John <j@example.com>").
    # This is acceptable for personal CLI use where addresses are well-formed.
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject

    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)

    # Set threading headers when replying to an existing message
    if reply_to_message:
        msg["In-Reply-To"] = reply_to_message.message_id
        # References should chain the full thread; fall back to the message ID
        # if no existing References header is present
        references = reply_to_message.in_reply_to or reply_to_message.message_id
        msg["References"] = references

    return msg


def create_draft(client: GmailClient, mime_message) -> str:
    """Create a Gmail draft via the API.

    Thin wrapper around GmailClient.create_draft.

    Args:
        client: Authenticated GmailClient.
        mime_message: MIME message object (from build_draft_message).

    Returns:
        Draft ID string (e.g. "r123456789").
    """
    return client.create_draft(mime_message)
