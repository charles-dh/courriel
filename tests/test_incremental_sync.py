"""Tests for incremental sync functionality.

Tests the History API integration and sync mode selection.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from courriel.storage.maildir import MaildirStorage
from courriel.sync.engine import SyncEngine
from courriel.sync.gmail import HttpError
from courriel.sync.state import SyncState


@pytest.fixture
def gmail_client() -> MagicMock:
    """Create a mock Gmail client."""
    return MagicMock()


@pytest.fixture
def maildir(tmp_path: Path) -> MaildirStorage:
    """Create a real Maildir storage with tmp directory."""
    return MaildirStorage(tmp_path / "Mail")


@pytest.fixture
def state(tmp_path: Path) -> SyncState:
    """Create a SyncState with temporary storage."""
    state_dir = tmp_path / "sync-state"
    state_dir.mkdir()
    with patch("courriel.sync.state.SYNC_STATE_DIR", state_dir):
        return SyncState("test")


@pytest.fixture
def engine(
    gmail_client: MagicMock, maildir: MaildirStorage, state: SyncState
) -> SyncEngine:
    """Create a SyncEngine with mocked Gmail client."""
    return SyncEngine(gmail_client, maildir, state)


class TestSyncModeSelection:
    """Tests for automatic sync mode selection."""

    def test_uses_full_sync_when_no_history_id(
        self, engine: SyncEngine, gmail_client: MagicMock
    ):
        """sync() uses full_sync when no previous sync exists."""
        gmail_client.list_messages.return_value = []

        engine.sync(["INBOX"])

        # Should call list_messages (full sync), not list_history
        gmail_client.list_messages.assert_called()
        gmail_client.list_history.assert_not_called()

    def test_uses_incremental_sync_when_history_id_exists(
        self, engine: SyncEngine, gmail_client: MagicMock, tmp_path: Path
    ):
        """sync() uses incremental_sync when history ID exists."""
        # Set up existing history ID
        with patch("courriel.sync.state.SYNC_STATE_DIR", tmp_path / "sync-state"):
            engine._state.save("12345", ["INBOX"])

            # Mock history response with no new messages
            gmail_client.list_history.return_value = {
                "history": [],
                "historyId": "12346",
            }

            engine.sync(["INBOX"])

        # Should call list_history (incremental), not list_messages
        gmail_client.list_history.assert_called()
        gmail_client.list_messages.assert_not_called()

    def test_uses_full_sync_when_date_filter_provided(
        self, engine: SyncEngine, gmail_client: MagicMock, tmp_path: Path
    ):
        """sync() uses full_sync when date filters are provided."""
        # Set up existing history ID
        with patch("courriel.sync.state.SYNC_STATE_DIR", tmp_path / "sync-state"):
            engine._state.save("12345", ["INBOX"])
            gmail_client.list_messages.return_value = []

            engine.sync(["INBOX"], days=30)

        # Should use full sync due to date filter
        gmail_client.list_messages.assert_called()
        gmail_client.list_history.assert_not_called()

    def test_uses_full_sync_when_force_full_true(
        self, engine: SyncEngine, gmail_client: MagicMock, tmp_path: Path
    ):
        """sync() uses full_sync when force_full=True."""
        with patch("courriel.sync.state.SYNC_STATE_DIR", tmp_path / "sync-state"):
            engine._state.save("12345", ["INBOX"])
            gmail_client.list_messages.return_value = []

            engine.sync(["INBOX"], force_full=True)

        gmail_client.list_messages.assert_called()
        gmail_client.list_history.assert_not_called()


class TestIncrementalSync:
    """Tests for incremental_sync method."""

    def test_fetches_only_new_messages(
        self, engine: SyncEngine, gmail_client: MagicMock, tmp_path: Path
    ):
        """incremental_sync only downloads messages from history."""
        with patch("courriel.sync.state.SYNC_STATE_DIR", tmp_path / "sync-state"):
            engine._state.save("100", ["INBOX"])

            # Mock history response with new messages
            gmail_client.list_history.return_value = {
                "history": [
                    {"messagesAdded": [{"message": {"id": "msg1"}}]},
                    {"messagesAdded": [{"message": {"id": "msg2"}}]},
                ],
                "historyId": "102",
            }
            gmail_client.get_message.side_effect = [
                {"id": "msg1", "labelIds": ["INBOX"], "raw": b"Message 1"},
                {"id": "msg2", "labelIds": ["INBOX"], "raw": b"Message 2"},
            ]

            result = engine.incremental_sync(["INBOX"])

        assert result.downloaded == 2
        assert result.skipped == 0
        assert result.errors == 0

    def test_handles_no_new_messages(
        self, engine: SyncEngine, gmail_client: MagicMock, tmp_path: Path
    ):
        """incremental_sync handles empty history gracefully."""
        with patch("courriel.sync.state.SYNC_STATE_DIR", tmp_path / "sync-state"):
            engine._state.save("100", ["INBOX"])

            gmail_client.list_history.return_value = {
                "history": [],
                "historyId": "100",
            }

            result = engine.incremental_sync(["INBOX"])

        assert result.downloaded == 0
        assert result.skipped == 0
        assert result.errors == 0

    def test_deduplicates_message_ids(
        self, engine: SyncEngine, gmail_client: MagicMock, tmp_path: Path
    ):
        """incremental_sync deduplicates messages appearing in multiple labels."""
        with patch("courriel.sync.state.SYNC_STATE_DIR", tmp_path / "sync-state"):
            engine._state.save("100", ["INBOX", "SENT"])

            # Same message appears in history for both labels
            gmail_client.list_history.side_effect = [
                {
                    "history": [{"messagesAdded": [{"message": {"id": "msg1"}}]}],
                    "historyId": "101",
                },
                {
                    "history": [{"messagesAdded": [{"message": {"id": "msg1"}}]}],
                    "historyId": "102",
                },
            ]
            gmail_client.get_message.return_value = {
                "id": "msg1",
                "labelIds": ["INBOX", "SENT"],
                "raw": b"Message 1",
            }

            result = engine.incremental_sync(["INBOX", "SENT"])

        # Should only download once despite appearing in both labels
        assert result.downloaded == 1
        assert gmail_client.get_message.call_count == 1

    def test_falls_back_to_full_sync_on_404(
        self, engine: SyncEngine, gmail_client: MagicMock, tmp_path: Path
    ):
        """incremental_sync falls back to full_sync when historyId expired."""
        with patch("courriel.sync.state.SYNC_STATE_DIR", tmp_path / "sync-state"):
            engine._state.save("old_expired_id", ["INBOX"])

            # Create a mock HttpError with 404 status
            mock_resp = MagicMock()
            mock_resp.status = 404
            http_error = HttpError(mock_resp, b"Not Found")

            gmail_client.list_history.side_effect = http_error
            gmail_client.list_messages.return_value = ["msg1"]
            gmail_client.get_message.return_value = {
                "id": "msg1",
                "labelIds": ["INBOX"],
                "historyId": "200",
                "raw": b"Message 1",
            }

            result = engine.incremental_sync(["INBOX"])

        # Should fall back to full sync
        gmail_client.list_messages.assert_called()
        assert result.downloaded == 1

    def test_updates_history_id_after_sync(
        self, engine: SyncEngine, gmail_client: MagicMock, tmp_path: Path
    ):
        """incremental_sync updates historyId after successful sync."""
        with patch("courriel.sync.state.SYNC_STATE_DIR", tmp_path / "sync-state"):
            engine._state.save("100", ["INBOX"])

            gmail_client.list_history.return_value = {
                "history": [{"messagesAdded": [{"message": {"id": "msg1"}}]}],
                "historyId": "200",
            }
            gmail_client.get_message.return_value = {
                "id": "msg1",
                "labelIds": ["INBOX"],
                "raw": b"Message",
            }

            engine.incremental_sync(["INBOX"])
            new_history_id = engine._state.get_history_id()

        assert new_history_id == "200"

    def test_skips_existing_messages(
        self,
        engine: SyncEngine,
        gmail_client: MagicMock,
        maildir: MaildirStorage,
        tmp_path: Path,
    ):
        """incremental_sync skips messages that already exist locally."""
        # Pre-write a message
        maildir.ensure_folder("INBOX")
        maildir.write_message("INBOX", b"existing", ["INBOX"], "msg1")

        with patch("courriel.sync.state.SYNC_STATE_DIR", tmp_path / "sync-state"):
            engine._state.save("100", ["INBOX"])

            gmail_client.list_history.return_value = {
                "history": [
                    {"messagesAdded": [{"message": {"id": "msg1"}}]},
                    {"messagesAdded": [{"message": {"id": "msg2"}}]},
                ],
                "historyId": "102",
            }
            gmail_client.get_message.return_value = {
                "id": "msg2",
                "labelIds": ["INBOX"],
                "raw": b"New message",
            }

            result = engine.incremental_sync(["INBOX"])

        assert result.downloaded == 1
        assert result.skipped == 1
        # get_message should only be called for msg2
        assert gmail_client.get_message.call_count == 1

    def test_calls_progress_callback(
        self, engine: SyncEngine, gmail_client: MagicMock, tmp_path: Path
    ):
        """incremental_sync calls progress callback during sync."""
        with patch("courriel.sync.state.SYNC_STATE_DIR", tmp_path / "sync-state"):
            engine._state.save("100", ["INBOX"])

            gmail_client.list_history.return_value = {
                "history": [
                    {"messagesAdded": [{"message": {"id": "msg1"}}]},
                    {"messagesAdded": [{"message": {"id": "msg2"}}]},
                ],
                "historyId": "102",
            }
            gmail_client.get_message.return_value = {
                "id": "msgX",
                "labelIds": ["INBOX"],
                "raw": b"Message",
            }

            progress_updates = []

            def track_progress(label: str, current: int, total: int):
                progress_updates.append((label, current, total))

            engine.incremental_sync(["INBOX"], progress_callback=track_progress)

        assert len(progress_updates) == 2
        assert progress_updates[0] == ("incremental", 1, 2)
        assert progress_updates[1] == ("incremental", 2, 2)

    def test_handles_api_errors_gracefully(
        self, engine: SyncEngine, gmail_client: MagicMock, tmp_path: Path
    ):
        """incremental_sync continues on individual message errors."""
        with patch("courriel.sync.state.SYNC_STATE_DIR", tmp_path / "sync-state"):
            engine._state.save("100", ["INBOX"])

            gmail_client.list_history.return_value = {
                "history": [
                    {"messagesAdded": [{"message": {"id": "msg1"}}]},
                    {"messagesAdded": [{"message": {"id": "msg2"}}]},
                ],
                "historyId": "102",
            }

            # One message fails, one succeeds - use a function to return based on ID
            def get_message_mock(msg_id):
                if msg_id == "msg1":
                    raise Exception("Network error")
                return {"id": msg_id, "labelIds": ["INBOX"], "raw": b"Message 2"}

            gmail_client.get_message.side_effect = get_message_mock

            result = engine.incremental_sync(["INBOX"])

        assert result.downloaded == 1
        assert result.errors == 1
        assert "msg1" in result.error_details[0]
        assert "Network error" in result.error_details[0]
