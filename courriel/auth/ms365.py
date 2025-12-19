"""Microsoft 365 authentication via MSAL Device Code Flow.

Handles authentication with Microsoft 365 using the Device Code Flow,
which is ideal for CLI applications. The user gets a code and URL,
authenticates in their browser, and the CLI receives tokens.

Token caching is handled by MSAL's SerializableTokenCache, which we
persist to ~/.config/courriel/credentials/ms365_cache.json
"""

import os
import sys

import msal

from courriel.config.paths import MS365_CACHE_FILE, ensure_credentials_dir

# Microsoft Graph scopes required for email operations.
# - User.Read: Get user profile info (for displaying logged-in user)
# - Mail.ReadWrite: Read and draft emails
# Note: offline_access is handled automatically by MSAL when using token cache
SCOPES = ["User.Read", "Mail.ReadWrite"]

# Environment variable for client secret.
# Using env var is preferred over storing in config.toml for security.
CLIENT_SECRET_ENV = "COURRIEL_MS365_CLIENT_SECRET"


def _load_token_cache() -> msal.SerializableTokenCache:
    """Load the token cache from disk.

    Returns an empty cache if the cache file doesn't exist.
    MSAL handles token refresh automatically when using the cache.
    """
    cache = msal.SerializableTokenCache()

    if MS365_CACHE_FILE.exists():
        cache.deserialize(MS365_CACHE_FILE.read_text())

    return cache


def _save_token_cache(cache: msal.SerializableTokenCache) -> None:
    """Persist the token cache to disk.

    Sets file permissions to 600 (owner read/write only) to protect tokens.
    """
    ensure_credentials_dir()

    MS365_CACHE_FILE.write_text(cache.serialize())
    # Restrictive permissions: only owner can read/write
    MS365_CACHE_FILE.chmod(0o600)


def get_client_secret(account_config: dict) -> str | None:
    """Get client secret from environment variable or config.

    Environment variable takes precedence for security - secrets in
    environment variables are less likely to be accidentally committed.

    Args:
        account_config: Account configuration dictionary.

    Returns:
        Client secret string, or None if not configured.
    """
    return os.environ.get(CLIENT_SECRET_ENV) or account_config.get("client_secret")


def _build_msal_app(
    client_id: str,
    tenant_id: str,
    cache: msal.SerializableTokenCache | None = None,
) -> msal.PublicClientApplication:
    """Build an MSAL PublicClientApplication.

    Device Code Flow uses PublicClientApplication regardless of whether
    we have a client secret, because the flow itself is designed for
    public clients (devices that can't securely store secrets).

    Args:
        client_id: Azure app registration client/application ID.
        tenant_id: Azure tenant/directory ID.
        cache: Optional token cache for persistence.

    Returns:
        Configured MSAL application instance.
    """
    authority = f"https://login.microsoftonline.com/{tenant_id}"

    return msal.PublicClientApplication(
        client_id=client_id,
        authority=authority,
        token_cache=cache,
    )


def authenticate_device_flow(
    client_id: str,
    tenant_id: str,
) -> dict:
    """Perform Device Code Flow authentication.

    Displays a code and URL for the user to authenticate in their browser.
    Blocks until authentication completes or times out (typically 15 minutes).

    If valid cached tokens exist, returns them without prompting.

    Args:
        client_id: Azure app registration client/application ID.
        tenant_id: Azure tenant/directory ID.

    Returns:
        Authentication result dict containing:
        - On success: 'access_token', 'id_token_claims', etc.
        - On failure: 'error' and 'error_description'
    """
    cache = _load_token_cache()
    app = _build_msal_app(client_id, tenant_id, cache)

    # Check for existing cached token first
    accounts = app.get_accounts()
    if accounts:
        # Try to get token silently from cache (may refresh if expired)
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            # Save cache in case token was refreshed
            if cache.has_state_changed:
                _save_token_cache(cache)
            return result

    # No cached token or refresh failed, start device flow
    flow = app.initiate_device_flow(scopes=SCOPES)

    if "user_code" not in flow:
        return {
            "error": "device_flow_failed",
            "error_description": flow.get(
                "error_description", "Failed to initiate device flow"
            ),
        }

    # Display the message to user (contains URL and code)
    # MSAL provides a nicely formatted message like:
    # "To sign in, use a web browser to open the page https://microsoft.com/devicelogin
    #  and enter the code XXXXXXXX to authenticate."
    print(flow["message"])
    sys.stdout.flush()

    # Block until user completes authentication or timeout
    result = app.acquire_token_by_device_flow(flow)

    # Save the updated cache with new tokens
    if cache.has_state_changed:
        _save_token_cache(cache)

    return result


def get_access_token(client_id: str, tenant_id: str) -> str | None:
    """Get a valid access token using cached credentials.

    Silently refreshes the token if expired. Does not prompt for login.
    Use authenticate_device_flow() first to establish credentials.

    Args:
        client_id: Azure app registration client/application ID.
        tenant_id: Azure tenant/directory ID.

    Returns:
        Access token string, or None if not authenticated.
    """
    cache = _load_token_cache()
    app = _build_msal_app(client_id, tenant_id, cache)

    accounts = app.get_accounts()
    if not accounts:
        return None

    result = app.acquire_token_silent(SCOPES, account=accounts[0])

    if result and "access_token" in result:
        # Save cache in case token was refreshed
        if cache.has_state_changed:
            _save_token_cache(cache)
        return result["access_token"]

    return None


def is_authenticated(client_id: str, tenant_id: str) -> bool:
    """Check if we have valid cached credentials.

    Does not attempt to refresh - just checks if tokens exist.

    Args:
        client_id: Azure app registration client/application ID.
        tenant_id: Azure tenant/directory ID.

    Returns:
        True if valid cached credentials exist.
    """
    return get_access_token(client_id, tenant_id) is not None
