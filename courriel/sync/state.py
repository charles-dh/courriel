"""Sync state management for incremental synchronization.

Stores the historyId from Gmail's History API to enable efficient
incremental syncs. Each account has its own state file.

State is stored in ~/.config/courriel/sync-state/<account>.json
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from courriel.config.paths import CONFIG_DIR


# Sync state directory
SYNC_STATE_DIR = CONFIG_DIR / "sync-state"


def ensure_sync_state_dir() -> Path:
    """Create sync state directory with restricted permissions.

    Sets directory permissions to 700 (owner read/write/execute only)
    to protect sync state data.

    Returns:
        Path to the sync state directory.
    """
    SYNC_STATE_DIR.mkdir(parents=True, exist_ok=True)
    SYNC_STATE_DIR.chmod(0o700)
    return SYNC_STATE_DIR


class SyncState:
    """Manages sync state for an account.

    Tracks the Gmail historyId to enable incremental synchronization.
    The History API returns changes since the stored historyId, avoiding
    the need to re-download all messages on each sync.

    State file format:
    {
        "history_id": "12345678",
        "last_sync": "2024-01-15T10:30:00Z",
        "synced_labels": ["INBOX", "SENT", "DRAFT"]
    }

    Example:
        state = SyncState("personal")
        history_id = state.get_history_id()  # None on first run
        # ... perform sync ...
        state.save("12345678", ["INBOX", "SENT"])
    """

    def __init__(self, account_name: str):
        """Initialize sync state for an account.

        Args:
            account_name: Name of the account (used for state file name).
        """
        self._account_name = account_name
        self._state_file = SYNC_STATE_DIR / f"{account_name}.json"
        self._state: dict | None = None

    @property
    def state_file(self) -> Path:
        """Get the path to this account's state file."""
        return self._state_file

    def load(self) -> dict | None:
        """Load sync state from disk.

        Returns:
            State dict with history_id, last_sync, synced_labels,
            or None if no state file exists.
        """
        if not self._state_file.exists():
            self._state = None
            return None

        try:
            self._state = json.loads(self._state_file.read_text())
            return self._state
        except (json.JSONDecodeError, OSError):
            # Corrupted or unreadable file - treat as no state
            self._state = None
            return None

    def save(self, history_id: str, synced_labels: list[str]) -> None:
        """Save sync state to disk.

        Updates the state file with the new historyId and records
        the current timestamp as last_sync.

        Args:
            history_id: Gmail History API ID from latest sync.
            synced_labels: List of labels that were synced.
        """
        ensure_sync_state_dir()

        self._state = {
            "history_id": history_id,
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "synced_labels": synced_labels,
        }

        self._state_file.write_text(json.dumps(self._state, indent=2))
        # Restrictive permissions for state file
        self._state_file.chmod(0o600)

    def get_history_id(self) -> str | None:
        """Get the stored history ID for incremental sync.

        Loads state from disk if not already loaded.

        Returns:
            History ID string, or None if no previous sync.
        """
        if self._state is None:
            self.load()

        if self._state is None:
            return None

        return self._state.get("history_id")

    def get_last_sync(self) -> datetime | None:
        """Get the timestamp of the last sync.

        Returns:
            Datetime of last sync, or None if no previous sync.
        """
        if self._state is None:
            self.load()

        if self._state is None:
            return None

        last_sync = self._state.get("last_sync")
        if last_sync:
            return datetime.fromisoformat(last_sync)

        return None

    def clear(self) -> None:
        """Clear sync state (forces full sync on next run).

        Deletes the state file if it exists.
        """
        if self._state_file.exists():
            self._state_file.unlink()
        self._state = None
