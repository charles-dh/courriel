"""Data models for search results."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SearchResult:
    """A single search result from local or remote search.

    Represents an email message with metadata and a body snippet.
    Used by both local (notmuch) and remote (Gmail API) search backends.
    """

    id: str  # Message ID (e.g., "abc123@example.com")
    account: str  # Account name from config
    file: str | None  # Local file path (local search only)
    date: datetime
    from_addr: str  # Full "Name <email>" format
    to_addrs: list[str] = field(default_factory=list)
    subject: str = ""
    snippet: str = ""  # Body preview (~200 chars)
    tags: list[str] = field(default_factory=list)  # notmuch tags / Gmail labels
    attachments: list[str] = field(default_factory=list)  # Attachment filenames

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "account": self.account,
            "file": self.file,
            "date": self.date.isoformat(),
            "from": self.from_addr,
            "to": self.to_addrs,
            "subject": self.subject,
            "snippet": self.snippet,
            "tags": self.tags,
            "attachments": self.attachments,
        }
