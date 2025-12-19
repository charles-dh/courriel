"""Path constants and directory utilities for courriel config.

Follows the XDG Base Directory specification:
- Config: ~/.config/courriel/
- Credentials: ~/.config/courriel/credentials/ (with restricted permissions)
"""

from pathlib import Path


# XDG-compliant config directory
CONFIG_DIR = Path.home() / ".config" / "courriel"
CONFIG_FILE = CONFIG_DIR / "config.toml"

# Credentials stored separately with restricted permissions
CREDENTIALS_DIR = CONFIG_DIR / "credentials"
MS365_CACHE_FILE = CREDENTIALS_DIR / "ms365_cache.json"
GMAIL_TOKEN_FILE = CREDENTIALS_DIR / "gmail_token.json"


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
