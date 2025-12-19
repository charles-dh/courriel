"""Configuration schema definitions.

Uses TypedDict for type safety without runtime overhead.
These types match the structure of config.toml.
"""

from typing import TypedDict


class DefaultsConfig(TypedDict, total=False):
    """Default settings applied to all operations.

    Attributes:
        max_messages: Maximum number of messages to sync per folder.
        days: Number of days of history to sync.
    """

    max_messages: int
    days: int


class AccountConfig(TypedDict, total=False):
    """Single email account configuration.

    Attributes:
        provider: Email provider ("ms365" or future "gmail").
        tenant_id: Microsoft 365 tenant/directory ID.
        client_id: Azure app registration client/application ID.
        client_secret: Optional client secret (prefer env var).
        mail_dir: Local Maildir path for this account (e.g., "~/Mail/Work").
    """

    provider: str
    tenant_id: str
    client_id: str
    client_secret: str
    mail_dir: str


class CourrielConfig(TypedDict, total=False):
    """Root configuration structure.

    Attributes:
        defaults: Default settings for all operations.
        accounts: Dict mapping account names to their configurations.
    """

    defaults: DefaultsConfig
    accounts: dict[str, AccountConfig]
