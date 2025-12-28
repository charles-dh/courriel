"""Sync engine for email synchronization.

Coordinates fetching emails from Gmail and storing them in Maildir.
Supports both full sync (initial) and incremental sync (subsequent).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta

from courriel.storage.maildir import MaildirStorage
from courriel.sync.gmail import GmailClient
from courriel.sync.state import SyncState


@dataclass
class SyncResult:
    """Result of a sync operation.

    Tracks counts of messages processed and any errors encountered.
    """

    downloaded: int = 0
    skipped: int = 0
    errors: int = 0
    error_details: list[str] = field(default_factory=list)

    def add_error(self, message_id: str, error: str) -> None:
        """Record an error for a specific message.

        Args:
            message_id: ID of the message that failed.
            error: Error description.
        """
        self.errors += 1
        self.error_details.append(f"{message_id}: {error}")


# Type for progress callback: (label, current, total) -> None
ProgressCallback = Callable[[str, int, int], None]


class SyncEngine:
    """Engine for synchronizing emails from Gmail to Maildir.

    Coordinates the Gmail client for fetching and Maildir storage
    for writing. Manages sync state for incremental synchronization.

    Example:
        creds = get_credentials()
        client = GmailClient(creds)
        storage = MaildirStorage(Path("~/Mail/Personal"))
        state = SyncState("personal")
        engine = SyncEngine(client, storage, state)

        result = engine.full_sync(["INBOX", "SENT"], max_messages=100)
        print(f"Downloaded {result.downloaded} messages")
    """

    def __init__(
        self,
        gmail_client: GmailClient,
        maildir: MaildirStorage,
        state: SyncState,
    ):
        """Initialize sync engine.

        Args:
            gmail_client: Gmail API client for fetching emails.
            maildir: Maildir storage for writing emails.
            state: Sync state manager for tracking history ID.
        """
        self._gmail = gmail_client
        self._maildir = maildir
        self._state = state

    def _build_query(
        self,
        since: date | None = None,
        days: int | None = None,
    ) -> str | None:
        """Build a Gmail search query for date filtering.

        Args:
            since: Sync messages after this date.
            days: Sync messages from the last N days.

        Returns:
            Gmail query string (e.g., "after:2024/01/01"), or None if no filter.
        """
        if since is not None:
            # Gmail query format: after:YYYY/MM/DD
            return f"after:{since.year}/{since.month:02d}/{since.day:02d}"

        if days is not None:
            # Calculate date from today
            target_date = date.today() - timedelta(days=days)
            return f"after:{target_date.year}/{target_date.month:02d}/{target_date.day:02d}"

        return None

    def full_sync(
        self,
        labels: list[str],
        max_messages: int = 100,
        query: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> SyncResult:
        """Perform a full sync of specified labels.

        Downloads all messages matching the criteria, skipping any
        that already exist in local storage.

        Args:
            labels: List of Gmail label IDs to sync (e.g., ["INBOX", "SENT"]).
            max_messages: Maximum messages to sync per label.
            query: Optional Gmail search query (e.g., "after:2024/01/01").
            progress_callback: Optional callback for progress updates.
                               Called with (label, current, total).

        Returns:
            SyncResult with counts of downloaded, skipped, and errored messages.
        """
        result = SyncResult()
        highest_history_id: str | None = None

        for label in labels:
            # Get message IDs for this label
            message_ids = self._gmail.list_messages(
                label_id=label,
                query=query,
                max_results=max_messages,
            )

            total = len(message_ids)

            for idx, message_id in enumerate(message_ids):
                # Report progress
                if progress_callback:
                    progress_callback(label, idx + 1, total)

                # Skip if already synced
                if self._maildir.message_exists(message_id):
                    result.skipped += 1
                    continue

                # Fetch full message
                try:
                    message = self._gmail.get_message(message_id)
                except Exception as e:
                    result.add_error(message_id, str(e))
                    continue

                # Track highest history ID for incremental sync
                msg_history_id = message.get("historyId")
                if msg_history_id:
                    if highest_history_id is None:
                        highest_history_id = msg_history_id
                    elif int(msg_history_id) > int(highest_history_id):
                        highest_history_id = msg_history_id

                # Determine target folder and write message
                try:
                    folder = self._maildir.get_primary_folder(message["labelIds"])
                    self._maildir.write_message(
                        folder=folder,
                        message_bytes=message["raw"],
                        label_ids=message["labelIds"],
                        message_id=message_id,
                    )
                    result.downloaded += 1
                except Exception as e:
                    result.add_error(message_id, str(e))

        # Save state for future incremental sync
        if highest_history_id:
            self._state.save(highest_history_id, labels)

        return result

    def sync(
        self,
        labels: list[str],
        max_messages: int = 100,
        since: date | None = None,
        days: int | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> SyncResult:
        """Main sync entry point.

        Automatically chooses between full and incremental sync based
        on whether a previous sync has been performed (historyId exists).

        For v1, this always performs a full sync. Incremental sync
        will be implemented in Milestone 4.

        Args:
            labels: List of Gmail label IDs to sync.
            max_messages: Maximum messages to sync per label.
            since: Optional date filter (sync messages after this date).
            days: Optional days filter (sync messages from last N days).
            progress_callback: Optional callback for progress updates.

        Returns:
            SyncResult with sync statistics.
        """
        # Build query from date filters
        query = self._build_query(since=since, days=days)

        # For now, always do full sync
        # Incremental sync will be added in Milestone 4
        return self.full_sync(
            labels=labels,
            max_messages=max_messages,
            query=query,
            progress_callback=progress_callback,
        )
