"""Authentication module for email providers.

Provides a provider-agnostic interface for authentication.
Supports Microsoft 365 and Gmail.

Usage:
    from courriel.auth import authenticate, get_access_token

    # Perform OAuth flow (interactive)
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

from .gmail import (
    authenticate_loopback_flow as _gmail_auth,
    get_access_token as _gmail_token,
    is_authenticated as _gmail_is_auth,
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

    For Gmail, uses OAuth 2.0 loopback flow - opens browser automatically
    and captures the authorization code via local HTTP server.

    Args:
        account: Account configuration from config.toml.

    Returns:
        Authentication result dict:
        - On success: contains 'access_token', plus provider-specific claims
        - On failure: contains 'error' and 'error_description'
    """
    provider = account.get("provider", "ms365")

    if provider == "ms365":
        client_id = account.get("client_id")
        tenant_id = account.get("tenant_id")

        if not client_id or not tenant_id:
            return {
                "error": "missing_config",
                "error_description": "MS365 account must have 'client_id' and 'tenant_id' configured.",
            }

        return _ms365_auth(client_id, tenant_id)

    elif provider == "gmail":
        client_id = account.get("client_id")

        if not client_id:
            return {
                "error": "missing_config",
                "error_description": "Gmail account must have 'client_id' configured.",
            }

        # Get client_secret from environment or config
        from .gmail import get_client_secret

        client_secret = get_client_secret(account)

        if not client_secret:
            return {
                "error": "missing_config",
                "error_description": "Gmail client_secret not found. Set COURRIEL_GMAIL_CLIENT_SECRET environment variable or add 'client_secret' to config.",
            }

        return _gmail_auth(client_id, client_secret)

    else:
        return {
            "error": "unsupported_provider",
            "error_description": f"Provider '{provider}' is not supported. Use 'ms365' or 'gmail'.",
        }


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

    if provider == "ms365":
        client_id = account.get("client_id")
        tenant_id = account.get("tenant_id")

        if not client_id or not tenant_id:
            return None

        return _ms365_token(client_id, tenant_id)

    elif provider == "gmail":
        client_id = account.get("client_id")

        if not client_id:
            return None

        from .gmail import get_client_secret

        client_secret = get_client_secret(account)

        if not client_secret:
            return None

        return _gmail_token(client_id, client_secret)

    else:
        return None


def is_authenticated(account: AccountConfig) -> bool:
    """Check if the account has valid cached credentials.

    Args:
        account: Account configuration from config.toml.

    Returns:
        True if valid credentials exist, False otherwise.
    """
    provider = account.get("provider", "ms365")

    if provider == "ms365":
        client_id = account.get("client_id")
        tenant_id = account.get("tenant_id")

        if not client_id or not tenant_id:
            return False

        return _ms365_is_auth(client_id, tenant_id)

    elif provider == "gmail":
        client_id = account.get("client_id")

        if not client_id:
            return False

        from .gmail import get_client_secret

        client_secret = get_client_secret(account)

        if not client_secret:
            return False

        return _gmail_is_auth(client_id, client_secret)

    else:
        return False
