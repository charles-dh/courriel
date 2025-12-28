"""Tests for Maildir storage.

Uses pytest tmp_path fixture for isolated filesystem tests.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from courriel.storage.maildir import MaildirStorage


@pytest.fixture
def storage(tmp_path: Path) -> MaildirStorage:
    """Create a MaildirStorage instance with a temporary directory."""
    return MaildirStorage(tmp_path)


class TestEnsureFolder:
    """Tests for ensure_folder method."""

    def test_creates_maildir_structure(self, storage: MaildirStorage):
        """ensure_folder creates cur/, new/, tmp/ subdirectories."""
        folder_path = storage.ensure_folder("INBOX")

        assert (folder_path / "cur").is_dir()
        assert (folder_path / "new").is_dir()
        assert (folder_path / "tmp").is_dir()

    def test_handles_nested_folders(self, storage: MaildirStorage):
        """ensure_folder creates nested folder structures."""
        folder_path = storage.ensure_folder("Labels/MyLabel")

        assert folder_path.name == "MyLabel"
        assert folder_path.parent.name == "Labels"
        assert (folder_path / "cur").is_dir()

    def test_idempotent_creation(self, storage: MaildirStorage):
        """ensure_folder can be called multiple times safely."""
        storage.ensure_folder("INBOX")
        storage.ensure_folder("INBOX")  # Should not raise

        assert (storage.base_path / "INBOX" / "cur").is_dir()


class TestLabelToFolder:
    """Tests for label_to_folder method."""

    def test_inbox_mapping(self, storage: MaildirStorage):
        """INBOX maps to INBOX folder."""
        assert storage.label_to_folder("INBOX") == "INBOX"

    def test_sent_mapping(self, storage: MaildirStorage):
        """SENT maps to Sent folder."""
        assert storage.label_to_folder("SENT") == "Sent"

    def test_draft_mapping(self, storage: MaildirStorage):
        """DRAFT maps to Drafts folder."""
        assert storage.label_to_folder("DRAFT") == "Drafts"

    def test_trash_mapping(self, storage: MaildirStorage):
        """TRASH maps to Trash folder."""
        assert storage.label_to_folder("TRASH") == "Trash"

    def test_spam_mapping(self, storage: MaildirStorage):
        """SPAM maps to Spam folder."""
        assert storage.label_to_folder("SPAM") == "Spam"

    def test_user_label_mapping(self, storage: MaildirStorage):
        """User labels map to Labels/<name>."""
        assert storage.label_to_folder("MyLabel") == "Labels/MyLabel"
        assert storage.label_to_folder("Work/Projects") == "Labels/Work/Projects"


class TestGetPrimaryFolder:
    """Tests for get_primary_folder method."""

    def test_inbox_priority(self, storage: MaildirStorage):
        """INBOX has highest priority."""
        labels = ["SENT", "INBOX", "UNREAD"]
        assert storage.get_primary_folder(labels) == "INBOX"

    def test_sent_priority(self, storage: MaildirStorage):
        """SENT has second priority after INBOX."""
        labels = ["SENT", "DRAFT", "UNREAD"]
        assert storage.get_primary_folder(labels) == "Sent"

    def test_draft_priority(self, storage: MaildirStorage):
        """DRAFT has third priority."""
        labels = ["DRAFT", "STARRED"]
        assert storage.get_primary_folder(labels) == "Drafts"

    def test_user_label_fallback(self, storage: MaildirStorage):
        """Falls back to first user label if no system labels."""
        labels = ["UNREAD", "STARRED", "MyLabel", "AnotherLabel"]
        assert storage.get_primary_folder(labels) == "Labels/MyLabel"

    def test_inbox_fallback(self, storage: MaildirStorage):
        """Falls back to INBOX if only virtual labels."""
        labels = ["UNREAD", "STARRED"]
        assert storage.get_primary_folder(labels) == "INBOX"


class TestLabelsToFlags:
    """Tests for labels_to_flags method."""

    def test_seen_flag_when_not_unread(self, storage: MaildirStorage):
        """Seen flag set when UNREAD label is absent."""
        flags = storage.labels_to_flags(["INBOX"])
        assert "S" in flags

    def test_no_seen_flag_when_unread(self, storage: MaildirStorage):
        """No Seen flag when UNREAD label is present."""
        flags = storage.labels_to_flags(["INBOX", "UNREAD"])
        assert "S" not in flags

    def test_flagged_from_starred(self, storage: MaildirStorage):
        """Flagged flag from STARRED label."""
        flags = storage.labels_to_flags(["INBOX", "STARRED"])
        assert "F" in flags

    def test_draft_flag(self, storage: MaildirStorage):
        """Draft flag from DRAFT label."""
        flags = storage.labels_to_flags(["DRAFT"])
        assert "D" in flags

    def test_trashed_flag(self, storage: MaildirStorage):
        """Trashed flag from TRASH label."""
        flags = storage.labels_to_flags(["TRASH"])
        assert "T" in flags

    def test_flags_alphabetically_sorted(self, storage: MaildirStorage):
        """Flags are sorted alphabetically."""
        flags = storage.labels_to_flags(["STARRED", "INBOX"])  # F and S
        assert flags == "FS"

    def test_multiple_flags(self, storage: MaildirStorage):
        """Multiple flags combined correctly."""
        flags = storage.labels_to_flags(["DRAFT", "STARRED"])  # D, F, and S
        assert flags == "DFS"


class TestGenerateFilename:
    """Tests for generate_filename method."""

    def test_filename_format(self, storage: MaildirStorage):
        """Filename follows <timestamp>.<id>.<hostname>:2,<flags> format."""
        with patch("courriel.storage.maildir.time.time", return_value=1704067200):
            filename = storage.generate_filename("abc123", "S")

        # Should match format: timestamp.message_id.hostname:2,flags
        parts = filename.split(".")
        assert parts[0] == "1704067200"  # timestamp
        assert parts[1] == "abc123"  # message_id
        assert ":2," in filename  # info2 format indicator
        assert filename.endswith("S")  # flags

    def test_includes_hostname(self, storage: MaildirStorage):
        """Filename includes hostname."""
        with patch(
            "courriel.storage.maildir.socket.gethostname", return_value="testhost"
        ):
            storage2 = MaildirStorage(storage.base_path)
            filename = storage2.generate_filename("msg1", "S")

        assert "testhost" in filename

    def test_empty_flags(self, storage: MaildirStorage):
        """Handles empty flags."""
        filename = storage.generate_filename("msg1", "")
        assert filename.endswith(":2,")


class TestWriteMessage:
    """Tests for write_message method."""

    def test_writes_to_correct_folder(self, storage: MaildirStorage):
        """Message written to specified folder."""
        message = b"From: test@example.com\r\nSubject: Test\r\n\r\nBody"

        path = storage.write_message("INBOX", message, ["INBOX"], "msg1")

        assert path.exists()
        assert "INBOX" in str(path)
        assert path.read_bytes() == message

    def test_unread_goes_to_new(self, storage: MaildirStorage):
        """Unread messages go to new/ directory."""
        message = b"Test message"

        path = storage.write_message("INBOX", message, ["INBOX", "UNREAD"], "msg1")

        assert path.parent.name == "new"

    def test_read_goes_to_cur(self, storage: MaildirStorage):
        """Read messages go to cur/ directory."""
        message = b"Test message"

        path = storage.write_message("INBOX", message, ["INBOX"], "msg1")

        assert path.parent.name == "cur"

    def test_atomic_write(self, storage: MaildirStorage):
        """Message not left in tmp/ after write."""
        message = b"Test message"

        storage.write_message("INBOX", message, ["INBOX"], "msg1")

        # tmp should be empty after write
        tmp_files = list((storage.base_path / "INBOX" / "tmp").iterdir())
        assert len(tmp_files) == 0

    def test_creates_folder_if_missing(self, storage: MaildirStorage):
        """write_message creates folder if it doesn't exist."""
        message = b"Test message"

        path = storage.write_message("NewFolder", message, ["INBOX"], "msg1")

        assert path.exists()
        assert (storage.base_path / "NewFolder" / "cur").is_dir()

    def test_flags_in_filename(self, storage: MaildirStorage):
        """Message filename includes correct flags."""
        message = b"Test message"

        path = storage.write_message("INBOX", message, ["INBOX", "STARRED"], "msg1")

        # Should have F (flagged) and S (seen) flags
        assert ":2,FS" in path.name


class TestMessageExists:
    """Tests for message_exists method."""

    def test_finds_existing_message(self, storage: MaildirStorage):
        """message_exists returns True for synced message."""
        message = b"Test message"
        storage.write_message("INBOX", message, ["INBOX"], "msg123")

        assert storage.message_exists("msg123") is True

    def test_not_found_for_missing(self, storage: MaildirStorage):
        """message_exists returns False for unknown message ID."""
        assert storage.message_exists("nonexistent") is False

    def test_finds_in_any_folder(self, storage: MaildirStorage):
        """message_exists finds message in any folder."""
        message = b"Test message"
        storage.write_message("Labels/Work", message, ["INBOX"], "msg456")

        assert storage.message_exists("msg456") is True

    def test_ignores_tmp_files(self, storage: MaildirStorage):
        """message_exists ignores files still in tmp/."""
        # Manually create a file in tmp (simulating interrupted write)
        storage.ensure_folder("INBOX")
        tmp_file = storage.base_path / "INBOX" / "tmp" / "123.msgX.host:2,S"
        tmp_file.write_bytes(b"test")

        assert storage.message_exists("msgX") is False


class TestGetMessagePath:
    """Tests for get_message_path method."""

    def test_returns_path_for_existing(self, storage: MaildirStorage):
        """get_message_path returns path for existing message."""
        message = b"Test message"
        written_path = storage.write_message("INBOX", message, ["INBOX"], "msg1")

        found_path = storage.get_message_path("msg1")

        assert found_path == written_path

    def test_returns_none_for_missing(self, storage: MaildirStorage):
        """get_message_path returns None for unknown message."""
        assert storage.get_message_path("nonexistent") is None
