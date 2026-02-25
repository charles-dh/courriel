"""Configuration management module.

Handles loading, saving, and accessing the courriel configuration.
Config is stored at ~/.config/courriel/config.toml

Usage:
    from courriel.config import load_config, save_config, get_account

    config = load_config()
    account = get_account(config, "work")
"""

import tomllib

import tomli_w

from .paths import CONFIG_FILE, ensure_config_dir
from .schema import AccountConfig, CourrielConfig
from .template import CONFIG_TEMPLATE

# Re-export for convenience
__all__ = [
    "load_config",
    "save_config",
    "init_config",
    "get_account",
    "get_account_names",
    "set_config_value",
    "CONFIG_FILE",
]

# Module-level cache for loaded config.
# Avoids repeated disk reads during a single CLI invocation.
_cached_config: CourrielConfig | None = None


def load_config(*, force_reload: bool = False) -> CourrielConfig:
    """Load configuration from disk.

    Returns empty dict if config file doesn't exist.
    Uses module-level caching to avoid repeated disk reads.

    Args:
        force_reload: Bypass cache and read from disk (useful after saving).

    Returns:
        The configuration dictionary.
    """
    global _cached_config

    if _cached_config is not None and not force_reload:
        return _cached_config

    if not CONFIG_FILE.exists():
        _cached_config = {}
        return _cached_config

    with open(CONFIG_FILE, "rb") as f:
        _cached_config = tomllib.load(f)

    return _cached_config


def save_config(config: CourrielConfig) -> None:
    """Save configuration to disk.

    Creates config directory if needed. Updates the module cache.

    Args:
        config: The configuration dictionary to save.
    """
    global _cached_config

    ensure_config_dir()

    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(config, f)

    # Keep cache in sync with disk
    _cached_config = config


def init_config(*, overwrite: bool = False) -> bool:
    """Initialize config directory and create template config file.

    Args:
        overwrite: If True, overwrite existing config file.

    Returns:
        True if config was created, False if it already existed.

    Raises:
        FileExistsError: If config exists and overwrite=False.
    """
    ensure_config_dir()

    if CONFIG_FILE.exists() and not overwrite:
        return False

    CONFIG_FILE.write_text(CONFIG_TEMPLATE)
    return True


def get_account(
    config: CourrielConfig, name: str | None = None
) -> AccountConfig | None:
    """Get account configuration by name.

    Args:
        config: The loaded configuration dictionary.
        name: Account name to retrieve. If None, returns the first account.

    Returns:
        The account configuration, or None if not found.
    """
    accounts = config.get("accounts", {})

    if not accounts:
        return None

    if name is None:
        # Return first account as default
        return next(iter(accounts.values()))

    return accounts.get(name)


def get_account_names(config: CourrielConfig) -> list[str]:
    """Get list of configured account names.

    Args:
        config: The loaded configuration dictionary.

    Returns:
        List of account names, may be empty.
    """
    return list(config.get("accounts", {}).keys())


def set_config_value(key: str, value: str) -> None:
    """Set a configuration value using dot notation.

    Examples:
        set_config_value("defaults.max_messages", "200")
        set_config_value("accounts.work.tenant_id", "xxx-xxx")

    Args:
        key: Dot-separated key path (e.g., "defaults.max_messages").
        value: Value to set (will be type-converted for known fields).

    Raises:
        ValueError: If value cannot be converted to expected type.
    """
    config = load_config(force_reload=True)

    parts = key.split(".")

    # Navigate to parent dict, creating intermediate dicts as needed
    current: dict = config
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]

    # Set the final value with type conversion
    final_key = parts[-1]
    converted_value = _convert_value(final_key, value)
    current[final_key] = converted_value

    save_config(config)


def _convert_value(key: str, value: str) -> str | int:
    """Convert string value to appropriate type based on field name.

    Known integer fields are converted to int, everything else stays str.

    Args:
        key: The field name (last part of dot notation key).
        value: The string value from CLI.

    Returns:
        Converted value (int for known numeric fields, str otherwise).

    Raises:
        ValueError: If value cannot be converted to expected type.
    """
    # Fields that should be integers
    int_fields = {"max_messages", "days", "search_limit"}

    if key in int_fields:
        return int(value)

    return value
