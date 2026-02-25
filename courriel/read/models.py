"""Data models for email message reading."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EmailMessage:
    """A fully parsed email message from a Maildir file.

    Contains all headers, body content, and attachment metadata.
    Used by the read command to display message contents.
    """

    file: str  # Path to the Maildir file
    date: datetime
    from_addr: str  # Full "Name <email>" format
    to_addrs: list[str] = field(default_factory=list)
    cc_addrs: list[str] = field(default_factory=list)
    bcc_addrs: list[str] = field(default_factory=list)
    subject: str = ""
    message_id: str = ""  # Message-ID header
    in_reply_to: str | None = None  # For threading
    body_plain: str | None = None  # text/plain content
    body_html: str | None = None  # text/html content
    attachments: list[dict] = field(default_factory=list)
    # Each attachment: {"filename": str, "content_type": str, "size": int}

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "file": self.file,
            "date": self.date.isoformat(),
            "from": self.from_addr,
            "to": self.to_addrs,
            "cc": self.cc_addrs,
            "bcc": self.bcc_addrs,
            "subject": self.subject,
            "message_id": self.message_id,
            "in_reply_to": self.in_reply_to,
            "body_plain": self.body_plain,
            "body_html": self.body_html,
            "attachments": self.attachments,
        }
