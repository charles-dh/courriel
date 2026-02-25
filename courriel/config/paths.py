"""Path constants and directory utilities for courriel config.

Follows the XDG Base Directory specification:
- Config: ~/.config/courriel/
- Credentials: ~/.config/courriel/credentials/ (with restricted permissions)
"""

import shutil
from pathlib import Path


# XDG-compliant config directory
CONFIG_DIR = Path.home() / ".config" / "courriel"
CONFIG_FILE = CONFIG_DIR / "config.toml"

# Credentials stored separately with restricted permissions
CREDENTIALS_DIR = CONFIG_DIR / "credentials"

# Legacy credential file paths (before per-account support).
# Kept here so the migration helper can find and rename them.
_LEGACY_GMAIL_TOKEN = CREDENTIALS_DIR / "gmail_token.json"
_LEGACY_MS365_CACHE = CREDENTIALS_DIR / "ms365_cache.json"


def gmail_token_file(account_name: str) -> Path:
    """Return the per-account Gmail token path.

    Args:
        account_name: Config key for the account (e.g. "personal", "work").

    Returns:
        Path like ``~/.config/courriel/credentials/gmail_token_personal.json``
    """
    return CREDENTIALS_DIR / f"gmail_token_{account_name}.json"


def ms365_cache_file(account_name: str) -> Path:
    """Return the per-account MS365 cache path.

    Args:
        account_name: Config key for the account (e.g. "personal", "work").

    Returns:
        Path like ``~/.config/courriel/credentials/ms365_cache_personal.json``
    """
    return CREDENTIALS_DIR / f"ms365_cache_{account_name}.json"


def migrate_credential_files(account_names: list[str]) -> None:
    """One-time migration: rename legacy credential files to per-account names.

    If the old ``gmail_token.json`` exists and no per-account files exist yet,
    copy it to ``gmail_token_{first_account}.json``.  Same for MS365.
    This avoids forcing re-authentication for existing users.

    Args:
        account_names: List of account names from config (e.g. ["personal"]).
    """
    if not account_names:
        return

    first = account_names[0]

    # Migrate Gmail token
    if _LEGACY_GMAIL_TOKEN.exists():
        target = gmail_token_file(first)
        if not target.exists():
            shutil.copy2(_LEGACY_GMAIL_TOKEN, target)
            target.chmod(0o600)

    # Migrate MS365 cache
    if _LEGACY_MS365_CACHE.exists():
        target = ms365_cache_file(first)
        if not target.exists():
            shutil.copy2(_LEGACY_MS365_CACHE, target)
            target.chmod(0o600)


def ensure_config_dir() -> Path:
    """Create config directory if it doesn't exist.

    Returns the config directory path.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def ensure_credentials_dir() -> Path:
    """Create credentials directory with restricted permissions.

    Sets directory permissions to 700 (owner read/write/execute only)
    to protect sensitive token data.

    Returns the credentials directory path.
    """
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    # Restrictive permissions: only owner can read/write/execute
    CREDENTIALS_DIR.chmod(0o700)
    return CREDENTIALS_DIR
