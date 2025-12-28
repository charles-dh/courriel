"""Tests for sync engine and sync state.

Tests SyncState for state persistence and SyncEngine for full sync.
"""

from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from courriel.storage.maildir import MaildirStorage
from courriel.sync.engine import SyncEngine, SyncResult
from courriel.sync.state import SyncState


class TestSyncState:
    """Tests for SyncState class."""

    @pytest.fixture
    def state_dir(self, tmp_path: Path) -> Path:
        """Create a temporary state directory."""
        state_dir = tmp_path / "sync-state"
        state_dir.mkdir()
        return state_dir

    @pytest.fixture
    def state(self, state_dir: Path) -> SyncState:
        """Create a SyncState with temporary storage."""
        with patch("courriel.sync.state.SYNC_STATE_DIR", state_dir):
            return SyncState("test-account")

    def test_load_returns_none_when_no_file(self, state: SyncState):
        """load() returns None when no state file exists."""
        result = state.load()
        assert result is None

    def test_save_and_load_roundtrip(self, state: SyncState, state_dir: Path):
        """save() persists state that can be loaded."""
        with patch("courriel.sync.state.SYNC_STATE_DIR", state_dir):
            state.save("12345", ["INBOX", "SENT"])

            # Create new state instance to test loading from disk
            state2 = SyncState("test-account")
            loaded = state2.load()

        assert loaded is not None
        assert loaded["history_id"] == "12345"
        assert loaded["synced_labels"] == ["INBOX", "SENT"]
        assert "last_sync" in loaded

    def test_get_history_id_returns_saved_value(
        self, state: SyncState, state_dir: Path
    ):
        """get_history_id() returns saved history ID."""
        with patch("courriel.sync.state.SYNC_STATE_DIR", state_dir):
            state.save("67890", ["INBOX"])
            history_id = state.get_history_id()

        assert history_id == "67890"

    def test_get_history_id_returns_none_when_no_state(self, state: SyncState):
        """get_history_id() returns None when no state exists."""
        assert state.get_history_id() is None

    def test_get_last_sync_returns_datetime(self, state: SyncState, state_dir: Path):
        """get_last_sync() returns datetime of last sync."""
        with patch("courriel.sync.state.SYNC_STATE_DIR", state_dir):
            state.save("12345", ["INBOX"])
            last_sync = state.get_last_sync()

        assert last_sync is not None
        assert isinstance(last_sync, datetime)
        # Should be recent (within last minute)
        assert (datetime.now(timezone.utc) - last_sync).total_seconds() < 60

    def test_clear_removes_state_file(self, state: SyncState, state_dir: Path):
        """clear() removes the state file."""
        with patch("courriel.sync.state.SYNC_STATE_DIR", state_dir):
            state.save("12345", ["INBOX"])
            state.clear()

        assert not state.state_file.exists()
        assert state.get_history_id() is None

    def test_handles_corrupted_state_file(self, state: SyncState, state_dir: Path):
        """load() handles corrupted state file gracefully."""
        with patch("courriel.sync.state.SYNC_STATE_DIR", state_dir):
            # Write invalid JSON
            state.state_file.parent.mkdir(parents=True, exist_ok=True)
            state.state_file.write_text("not valid json")

            result = state.load()

        assert result is None


class TestSyncResult:
    """Tests for SyncResult dataclass."""

    def test_default_values(self):
        """SyncResult has sensible defaults."""
        result = SyncResult()
        assert result.downloaded == 0
        assert result.skipped == 0
        assert result.errors == 0
        assert result.error_details == []

    def test_add_error(self):
        """add_error() increments count and records detail."""
        result = SyncResult()
        result.add_error("msg1", "Connection failed")

        assert result.errors == 1
        assert len(result.error_details) == 1
        assert "msg1" in result.error_details[0]
        assert "Connection failed" in result.error_details[0]


class TestSyncEngine:
    """Tests for SyncEngine class."""

    @pytest.fixture
    def gmail_client(self) -> MagicMock:
        """Create a mock Gmail client."""
        client = MagicMock()
        return client

    @pytest.fixture
    def maildir(self, tmp_path: Path) -> MaildirStorage:
        """Create a real Maildir storage with tmp directory."""
        return MaildirStorage(tmp_path / "Mail")

    @pytest.fixture
    def state(self, tmp_path: Path) -> SyncState:
        """Create a SyncState with temporary storage."""
        state_dir = tmp_path / "sync-state"
        state_dir.mkdir()
        with patch("courriel.sync.state.SYNC_STATE_DIR", state_dir):
            return SyncState("test")

    @pytest.fixture
    def engine(
        self, gmail_client: MagicMock, maildir: MaildirStorage, state: SyncState
    ) -> SyncEngine:
        """Create a SyncEngine with mocked Gmail client."""
        return SyncEngine(gmail_client, maildir, state)

    def test_build_query_with_since(self, engine: SyncEngine):
        """_build_query() builds query from since date."""
        query = engine._build_query(since=date(2024, 1, 15))
        assert query == "after:2024/01/15"

    def test_build_query_with_days(self, engine: SyncEngine):
        """_build_query() builds query from days parameter."""
        with patch("courriel.sync.engine.date") as mock_date:
            mock_date.today.return_value = date(2024, 6, 15)
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

            query = engine._build_query(days=30)

        assert query == "after:2024/05/16"

    def test_build_query_returns_none_when_no_filter(self, engine: SyncEngine):
        """_build_query() returns None when no date filter."""
        query = engine._build_query()
        assert query is None

    def test_full_sync_downloads_messages(
        self, engine: SyncEngine, gmail_client: MagicMock, maildir: MaildirStorage
    ):
        """full_sync() downloads and stores messages."""
        # Setup mock responses
        gmail_client.list_messages.return_value = ["msg1", "msg2"]
        gmail_client.get_message.side_effect = [
            {
                "id": "msg1",
                "threadId": "t1",
                "labelIds": ["INBOX"],
                "historyId": "100",
                "raw": b"From: test@example.com\r\nSubject: Test 1\r\n\r\nBody 1",
            },
            {
                "id": "msg2",
                "threadId": "t2",
                "labelIds": ["INBOX"],
                "historyId": "101",
                "raw": b"From: test@example.com\r\nSubject: Test 2\r\n\r\nBody 2",
            },
        ]

        result = engine.full_sync(["INBOX"], max_messages=10)

        assert result.downloaded == 2
        assert result.skipped == 0
        assert result.errors == 0
        # Verify messages were written
        assert maildir.message_exists("msg1")
        assert maildir.message_exists("msg2")

    def test_full_sync_skips_existing_messages(
        self, engine: SyncEngine, gmail_client: MagicMock, maildir: MaildirStorage
    ):
        """full_sync() skips messages that already exist."""
        # Pre-write a message
        maildir.ensure_folder("INBOX")
        maildir.write_message("INBOX", b"existing", ["INBOX"], "msg1")

        gmail_client.list_messages.return_value = ["msg1", "msg2"]
        gmail_client.get_message.return_value = {
            "id": "msg2",
            "threadId": "t2",
            "labelIds": ["INBOX"],
            "historyId": "100",
            "raw": b"New message",
        }

        result = engine.full_sync(["INBOX"], max_messages=10)

        assert result.downloaded == 1
        assert result.skipped == 1
        # get_message should only be called once (for msg2)
        assert gmail_client.get_message.call_count == 1

    def test_full_sync_saves_history_id(
        self, engine: SyncEngine, gmail_client: MagicMock, tmp_path: Path
    ):
        """full_sync() saves highest historyId for incremental sync."""
        gmail_client.list_messages.return_value = ["msg1", "msg2"]
        gmail_client.get_message.side_effect = [
            {
                "id": "msg1",
                "labelIds": ["INBOX"],
                "historyId": "100",
                "raw": b"Message 1",
            },
            {
                "id": "msg2",
                "labelIds": ["INBOX"],
                "historyId": "200",  # Higher history ID
                "raw": b"Message 2",
            },
        ]

        with patch("courriel.sync.state.SYNC_STATE_DIR", tmp_path / "sync-state"):
            engine.full_sync(["INBOX"], max_messages=10)
            history_id = engine._state.get_history_id()

        assert history_id == "200"

    def test_full_sync_handles_api_errors(
        self, engine: SyncEngine, gmail_client: MagicMock
    ):
        """full_sync() handles API errors gracefully."""
        gmail_client.list_messages.return_value = ["msg1", "msg2"]
        gmail_client.get_message.side_effect = [
            Exception("API error"),
            {
                "id": "msg2",
                "labelIds": ["INBOX"],
                "historyId": "100",
                "raw": b"Message 2",
            },
        ]

        result = engine.full_sync(["INBOX"], max_messages=10)

        assert result.downloaded == 1
        assert result.errors == 1
        assert "msg1" in result.error_details[0]

    def test_full_sync_calls_progress_callback(
        self, engine: SyncEngine, gmail_client: MagicMock
    ):
        """full_sync() calls progress callback with updates."""
        gmail_client.list_messages.return_value = ["msg1", "msg2"]
        gmail_client.get_message.return_value = {
            "id": "msg1",
            "labelIds": ["INBOX"],
            "historyId": "100",
            "raw": b"Message",
        }

        progress_updates = []

        def track_progress(label: str, current: int, total: int):
            progress_updates.append((label, current, total))

        engine.full_sync(["INBOX"], max_messages=10, progress_callback=track_progress)

        assert len(progress_updates) == 2
        assert progress_updates[0] == ("INBOX", 1, 2)
        assert progress_updates[1] == ("INBOX", 2, 2)

    def test_sync_uses_query_from_date_filters(
        self, engine: SyncEngine, gmail_client: MagicMock
    ):
        """sync() builds query from since/days parameters."""
        gmail_client.list_messages.return_value = []

        engine.sync(["INBOX"], since=date(2024, 3, 1))

        gmail_client.list_messages.assert_called_with(
            label_id="INBOX",
            query="after:2024/03/01",
            max_results=100,
        )

    def test_full_sync_multiple_labels(
        self, engine: SyncEngine, gmail_client: MagicMock, maildir: MaildirStorage
    ):
        """full_sync() processes multiple labels."""
        # Different messages for each label
        gmail_client.list_messages.side_effect = [
            ["inbox1"],  # INBOX
            ["sent1"],  # SENT
        ]
        gmail_client.get_message.side_effect = [
            {
                "id": "inbox1",
                "labelIds": ["INBOX"],
                "historyId": "100",
                "raw": b"Inbox message",
            },
            {
                "id": "sent1",
                "labelIds": ["SENT"],
                "historyId": "101",
                "raw": b"Sent message",
            },
        ]

        result = engine.full_sync(["INBOX", "SENT"], max_messages=10)

        assert result.downloaded == 2
        assert maildir.message_exists("inbox1")
        assert maildir.message_exists("sent1")
