"""Sync engine for email synchronization.

Coordinates fetching emails from Gmail and storing them in Maildir.
Supports both full sync (initial) and incremental sync (subsequent).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta

from courriel.storage.maildir import MaildirStorage
from courriel.sync.gmail import GmailClient, HttpError
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

    def incremental_sync(
        self,
        labels: list[str],
        progress_callback: ProgressCallback | None = None,
    ) -> SyncResult:
        """Perform an incremental sync using Gmail History API.

        Only fetches messages added since the last sync, based on the
        stored historyId. This is much more efficient than full sync
        for regular updates.

        If the historyId is expired (older than ~1 week), falls back
        to full sync automatically.

        Args:
            labels: List of Gmail label IDs to sync.
            progress_callback: Optional callback for progress updates.

        Returns:
            SyncResult with counts of downloaded, skipped, and errored messages.
        """
        result = SyncResult()
        start_history_id = self._state.get_history_id()

        if not start_history_id:
            # No previous sync - shouldn't happen, but fall back to full sync
            return self.full_sync(labels, progress_callback=progress_callback)

        # Collect all new message IDs from history
        new_message_ids: set[str] = set()
        current_history_id = start_history_id

        for label in labels:
            try:
                history_result = self._gmail.list_history(
                    start_history_id=start_history_id,
                    label_id=label,
                )
            except HttpError as e:
                # HTTP 404 means historyId is expired - fall back to full sync
                if e.resp.status == 404:
                    return self.full_sync(labels, progress_callback=progress_callback)
                raise

            # Extract message IDs from messagesAdded
            for record in history_result.get("history", []):
                for added in record.get("messagesAdded", []):
                    msg = added.get("message", {})
                    msg_id = msg.get("id")
                    if msg_id:
                        new_message_ids.add(msg_id)

            # Track latest history ID
            new_history_id = history_result.get("historyId")
            if new_history_id:
                if int(new_history_id) > int(current_history_id):
                    current_history_id = new_history_id

        # Download new messages
        message_list = list(new_message_ids)
        total = len(message_list)

        for idx, message_id in enumerate(message_list):
            # Report progress
            if progress_callback:
                progress_callback("incremental", idx + 1, total)

            # Skip if already exists (possible if interrupted mid-sync)
            if self._maildir.message_exists(message_id):
                result.skipped += 1
                continue

            # Fetch and store message
            try:
                message = self._gmail.get_message(message_id)
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

        # Update state with new history ID
        self._state.save(current_history_id, labels)

        return result

    def sync(
        self,
        labels: list[str],
        max_messages: int = 100,
        since: date | None = None,
        days: int | None = None,
        progress_callback: ProgressCallback | None = None,
        force_full: bool = False,
    ) -> SyncResult:
        """Main sync entry point.

        Automatically chooses between full and incremental sync based
        on whether a previous sync has been performed (historyId exists).

        - First sync: Full sync (downloads up to max_messages per label)
        - Subsequent syncs: Incremental sync (only new messages via History API)
        - If date filters provided: Full sync (incremental doesn't support filters)
        - If force_full=True: Full sync

        Args:
            labels: List of Gmail label IDs to sync.
            max_messages: Maximum messages to sync per label.
            since: Optional date filter (sync messages after this date).
            days: Optional days filter (sync messages from last N days).
            progress_callback: Optional callback for progress updates.
            force_full: Force a full sync even if incremental is available.

        Returns:
            SyncResult with sync statistics.
        """
        # Build query from date filters
        query = self._build_query(since=since, days=days)

        # Determine sync mode
        history_id = self._state.get_history_id()
        use_incremental = (
            history_id is not None
            and not force_full
            and query is None  # Incremental doesn't support date filters
        )

        if use_incremental:
            return self.incremental_sync(
                labels=labels,
                progress_callback=progress_callback,
            )
        else:
            return self.full_sync(
                labels=labels,
                max_messages=max_messages,
                query=query,
                progress_callback=progress_callback,
            )
