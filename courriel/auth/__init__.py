"""Authentication module for email providers.

Provides a provider-agnostic interface for authentication.
Currently supports Microsoft 365, with Gmail planned for future.

Usage:
    from courriel.auth import authenticate, get_access_token

    # Perform device code flow (interactive)
    result = authenticate(account_config)

    # Get cached access token (non-interactive)
    token = get_access_token(account_config)
"""

from courriel.config.schema import AccountConfig

from .ms365 import (
    authenticate_device_flow as _ms365_auth,
    get_access_token as _ms365_token,
    is_authenticated as _ms365_is_auth,
)

__all__ = [
    "authenticate",
    "get_access_token",
    "is_authenticated",
]


def authenticate(account: AccountConfig) -> dict:
    """Authenticate with the configured email provider.

    For Microsoft 365, uses Device Code Flow - displays a code and URL
    for the user to complete authentication in their browser.

    Args:
        account: Account configuration from config.toml.

    Returns:
        Authentication result dict:
        - On success: contains 'access_token', 'id_token_claims', etc.
        - On failure: contains 'error' and 'error_description'
    """
    provider = account.get("provider", "ms365")

    if provider != "ms365":
        return {
            "error": "unsupported_provider",
            "error_description": f"Provider '{provider}' is not supported. Use 'ms365'.",
        }

    client_id = account.get("client_id")
    tenant_id = account.get("tenant_id")

    if not client_id or not tenant_id:
        return {
            "error": "missing_config",
            "error_description": "Account must have 'client_id' and 'tenant_id' configured.",
        }

    return _ms365_auth(client_id, tenant_id)


def get_access_token(account: AccountConfig) -> str | None:
    """Get a valid access token for the account.

    Uses cached credentials and refreshes if needed.
    Does not prompt for login - use authenticate() first.

    Args:
        account: Account configuration from config.toml.

    Returns:
        Access token string, or None if not authenticated.
    """
    provider = account.get("provider", "ms365")

    if provider != "ms365":
        return None

    client_id = account.get("client_id")
    tenant_id = account.get("tenant_id")

    if not client_id or not tenant_id:
        return None

    return _ms365_token(client_id, tenant_id)


def is_authenticated(account: AccountConfig) -> bool:
    """Check if the account has valid cached credentials.

    Args:
        account: Account configuration from config.toml.

    Returns:
        True if valid credentials exist, False otherwise.
    """
    provider = account.get("provider", "ms365")

    if provider != "ms365":
        return False

    client_id = account.get("client_id")
    tenant_id = account.get("tenant_id")

    if not client_id or not tenant_id:
        return False

    return _ms365_is_auth(client_id, tenant_id)
