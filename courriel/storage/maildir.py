"""Maildir storage for email messages.

Implements Maildir format compatible with notmuch and standard mail tools.
Handles folder creation, message writing, and label-to-folder mapping.

Maildir format uses three subdirectories:
- tmp/: Messages being delivered (atomic write in progress)
- new/: Newly delivered, unread messages
- cur/: Messages that have been seen

Message filenames follow the format:
<timestamp>.<unique-id>.<hostname>:2,<flags>

Flags are single uppercase letters (alphabetically sorted):
- D: Draft
- F: Flagged (starred)
- R: Replied
- S: Seen (read)
- T: Trashed
"""

import os
import socket
import time
from pathlib import Path


# Gmail system labels mapped to Maildir folder names
# These are the standard mappings that work well with notmuch
LABEL_FOLDER_MAP = {
    "INBOX": "INBOX",
    "SENT": "Sent",
    "DRAFT": "Drafts",
    "TRASH": "Trash",
    "SPAM": "Spam",
}

# Gmail labels that map to Maildir flags instead of folders
# STARRED and IMPORTANT are treated as flags, not folders
LABEL_FLAG_MAP = {
    "STARRED": "F",  # Flagged
    "DRAFT": "D",  # Draft
    # UNREAD is special - absence means "Seen" flag should be set
}

# Priority order for determining primary folder when message has multiple labels
# INBOX takes precedence over SENT, which takes precedence over DRAFT
FOLDER_PRIORITY = ["INBOX", "SENT", "DRAFT", "TRASH", "SPAM"]


class MaildirStorage:
    """Storage backend for Maildir format.

    Manages folder structure and message storage for email synchronization.
    Messages are written atomically (tmp -> cur/new) to prevent corruption.

    Example:
        storage = MaildirStorage(Path("~/Mail/Personal"))
        storage.ensure_folder("INBOX")
        path = storage.write_message(
            "INBOX",
            message_bytes,
            ["INBOX", "UNREAD"]
        )
    """

    def __init__(self, base_path: Path):
        """Initialize Maildir storage.

        Args:
            base_path: Base directory for Maildir storage (e.g., ~/Mail/Personal).
                       Will be created if it doesn't exist.
        """
        self._base_path = base_path.expanduser().resolve()
        self._hostname = socket.gethostname()

    @property
    def base_path(self) -> Path:
        """Get the base path for this Maildir storage."""
        return self._base_path

    def ensure_folder(self, folder_name: str) -> Path:
        """Create a Maildir folder structure.

        Creates the folder with cur/, new/, tmp/ subdirectories as required
        by the Maildir specification. Safe to call multiple times.

        Args:
            folder_name: Folder name (e.g., "INBOX", "Sent", "Labels/MyLabel").

        Returns:
            Path to the folder directory.
        """
        folder_path = self._base_path / folder_name

        # Create Maildir subdirectories
        for subdir in ("cur", "new", "tmp"):
            (folder_path / subdir).mkdir(parents=True, exist_ok=True)

        return folder_path

    def label_to_folder(self, label_id: str) -> str:
        """Convert a Gmail label ID to a Maildir folder name.

        System labels (INBOX, SENT, etc.) map to standard folder names.
        User labels map to Labels/<name> for organization.

        Args:
            label_id: Gmail label ID or name.

        Returns:
            Maildir folder name (e.g., "INBOX", "Sent", "Labels/MyLabel").
        """
        # Check if it's a known system label
        if label_id in LABEL_FOLDER_MAP:
            return LABEL_FOLDER_MAP[label_id]

        # User labels go under Labels/ directory
        # Strip any leading/trailing whitespace and use as-is
        return f"Labels/{label_id}"

    def get_primary_folder(self, label_ids: list[str]) -> str:
        """Determine the primary folder for a message with multiple labels.

        Messages in Gmail can have multiple labels, but in Maildir they
        exist in a single folder. This method picks the most appropriate
        folder based on priority (INBOX > SENT > DRAFT > first custom label).

        Args:
            label_ids: List of Gmail label IDs on the message.

        Returns:
            The primary folder name for storing the message.
        """
        # Check system labels in priority order
        for label in FOLDER_PRIORITY:
            if label in label_ids:
                return self.label_to_folder(label)

        # Fall back to first user label (excluding virtual labels like UNREAD)
        virtual_labels = {
            "UNREAD",
            "STARRED",
            "IMPORTANT",
            "CATEGORY_PERSONAL",
            "CATEGORY_SOCIAL",
            "CATEGORY_PROMOTIONS",
            "CATEGORY_UPDATES",
            "CATEGORY_FORUMS",
        }

        for label in label_ids:
            if label not in virtual_labels and label not in LABEL_FOLDER_MAP:
                return self.label_to_folder(label)

        # Ultimate fallback to INBOX
        return "INBOX"

    def labels_to_flags(self, label_ids: list[str]) -> str:
        """Convert Gmail labels to Maildir flags.

        Gmail labels map to single-character flags in the filename.
        Flags are sorted alphabetically as per Maildir spec.

        Args:
            label_ids: List of Gmail label IDs.

        Returns:
            Alphabetically sorted flag string (e.g., "FS" for Flagged+Seen).
        """
        flags = set()

        # Check for Seen flag (absence of UNREAD label)
        if "UNREAD" not in label_ids:
            flags.add("S")

        # Check for other flags
        if "STARRED" in label_ids:
            flags.add("F")

        if "DRAFT" in label_ids:
            flags.add("D")

        if "TRASH" in label_ids:
            flags.add("T")

        # Return alphabetically sorted flags
        return "".join(sorted(flags))

    def generate_filename(self, message_id: str, flags: str) -> str:
        """Generate a Maildir-compliant filename for a message.

        Format: <timestamp>.<message_id>.<hostname>:2,<flags>

        The "2," prefix before flags indicates Maildir info2 format,
        which is the standard for storing flags in filenames.

        Args:
            message_id: Gmail message ID (used as unique identifier).
            flags: Maildir flags string (e.g., "FS").

        Returns:
            Complete filename for the message.
        """
        timestamp = int(time.time())
        return f"{timestamp}.{message_id}.{self._hostname}:2,{flags}"

    def write_message(
        self,
        folder: str,
        message_bytes: bytes,
        label_ids: list[str],
        message_id: str,
    ) -> Path:
        """Write a message to Maildir storage.

        Messages are written atomically: first to tmp/, then moved to
        either new/ (unread) or cur/ (read). This prevents corruption
        if the process is interrupted.

        Args:
            folder: Target folder name (e.g., "INBOX").
            message_bytes: Raw RFC 2822 message content.
            label_ids: Gmail labels for flag conversion.
            message_id: Gmail message ID for filename uniqueness.

        Returns:
            Path to the written message file.
        """
        # Ensure folder exists
        folder_path = self.ensure_folder(folder)

        # Generate flags and filename
        flags = self.labels_to_flags(label_ids)
        filename = self.generate_filename(message_id, flags)

        # Write to tmp first (atomic write pattern)
        tmp_path = folder_path / "tmp" / filename
        tmp_path.write_bytes(message_bytes)

        # Determine destination: new/ for unread, cur/ for read
        if "UNREAD" in label_ids:
            dest_dir = "new"
        else:
            dest_dir = "cur"

        dest_path = folder_path / dest_dir / filename

        # Atomic move from tmp to destination
        # os.rename is atomic on POSIX systems when src and dest are on same filesystem
        os.rename(tmp_path, dest_path)

        return dest_path

    def message_exists(self, message_id: str) -> bool:
        """Check if a message already exists in storage.

        Searches all folders for a file containing the message_id.
        Used to skip already-synced messages during full sync.

        Args:
            message_id: Gmail message ID to search for.

        Returns:
            True if a message with this ID exists in any folder.
        """
        # Search all directories recursively for the message ID
        # Message ID appears in filename: <timestamp>.<message_id>.<hostname>:2,<flags>
        for path in self._base_path.rglob(f"*.{message_id}.*"):
            # Verify it's in cur/ or new/ (not tmp/)
            if path.parent.name in ("cur", "new"):
                return True

        return False

    def get_message_path(self, message_id: str) -> Path | None:
        """Get the path to a specific message if it exists.

        Args:
            message_id: Gmail message ID to find.

        Returns:
            Path to the message file, or None if not found.
        """
        for path in self._base_path.rglob(f"*.{message_id}.*"):
            if path.parent.name in ("cur", "new"):
                return path

        return None
