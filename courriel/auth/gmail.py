"""Gmail authentication via OAuth 2.0 Installed Application Flow.

Handles authentication with Gmail using the OAuth 2.0 loopback redirect flow,
which is ideal for CLI applications. The user's browser opens to Google's
consent page, they authenticate, and the authorization code is captured via
a local HTTP server redirect.

Token caching is handled by google.oauth2.credentials, which we persist
to ~/.config/courriel/credentials/gmail_token.json
"""

import json
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from courriel.config.paths import GMAIL_TOKEN_FILE, ensure_credentials_dir

# Gmail API scopes required for email operations.
# - gmail.readonly: Read emails (for sync and search)
# - gmail.modify: Modify labels, mark as read/unread
# - gmail.compose: Create and send drafts (we only create, not send)
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
]

# Environment variable for client secret.
# Using env var is preferred over storing in config.toml for security.
CLIENT_SECRET_ENV = "COURRIEL_GMAIL_CLIENT_SECRET"

# Loopback redirect URI for installed applications
# Google recommends localhost:8080 for CLI apps
REDIRECT_URI = "http://localhost:8080"


def _load_token() -> Credentials | None:
    """Load credentials from disk.

    Returns None if the token file doesn't exist or is invalid.
    Google's Credentials class handles token refresh automatically.
    """
    if not GMAIL_TOKEN_FILE.exists():
        return None

    try:
        creds = Credentials.from_authorized_user_file(str(GMAIL_TOKEN_FILE), SCOPES)
        return creds
    except Exception:
        # Invalid token file - will re-authenticate
        return None


def _save_token(creds: Credentials) -> None:
    """Persist credentials to disk.

    Sets file permissions to 600 (owner read/write only) to protect tokens.
    """
    ensure_credentials_dir()

    # Convert credentials to JSON format
    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }

    GMAIL_TOKEN_FILE.write_text(json.dumps(token_data, indent=2))
    # Restrictive permissions: only owner can read/write
    GMAIL_TOKEN_FILE.chmod(0o600)


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


def _build_client_config(client_id: str, client_secret: str) -> dict:
    """Build OAuth client configuration dict.

    Google's InstalledAppFlow expects a specific JSON structure that
    normally comes from downloading credentials from Cloud Console.
    We construct it programmatically from our config values.

    Args:
        client_id: Google Cloud OAuth client ID.
        client_secret: Google Cloud OAuth client secret.

    Returns:
        Client configuration dict in the format expected by InstalledAppFlow.
    """
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    }


def authenticate_loopback_flow(
    client_id: str,
    client_secret: str,
) -> dict:
    """Perform OAuth 2.0 loopback flow authentication.

    Starts a local HTTP server on localhost:8080, opens the user's browser
    to Google's consent page, captures the authorization code from the redirect,
    and exchanges it for tokens.

    If valid cached tokens exist, returns them without prompting.

    Args:
        client_id: Google Cloud OAuth client ID.
        client_secret: Google Cloud OAuth client secret.

    Returns:
        Authentication result dict containing:
        - On success: 'access_token', 'refresh_token', 'email', etc.
        - On failure: 'error' and 'error_description'
    """
    # Check for existing cached token first
    creds = _load_token()

    if creds and creds.valid:
        # Token is still valid, return it
        return {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "email": getattr(creds, "_id_token_jwt", {}).get("email", "Unknown"),
        }

    if creds and creds.expired and creds.refresh_token:
        # Token expired but we can refresh it
        try:
            creds.refresh(Request())
            _save_token(creds)
            return {
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "email": getattr(creds, "_id_token_jwt", {}).get("email", "Unknown"),
            }
        except Exception:
            # Refresh failed, fall through to re-authenticate
            pass

    # No valid token, start OAuth flow
    try:
        client_config = _build_client_config(client_id, client_secret)
        flow = InstalledAppFlow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
        )

        # Run local server to capture OAuth callback
        # This will open the user's browser automatically
        creds = flow.run_local_server(
            port=8080,
            # Customize success message
            success_message="Authentication successful! You can close this window.",
        )

        # Save the credentials for future use
        _save_token(creds)

        return {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "email": getattr(creds, "_id_token_jwt", {}).get("email", "Unknown"),
        }

    except Exception as e:
        return {
            "error": "oauth_flow_failed",
            "error_description": f"OAuth 2.0 flow failed: {str(e)}",
        }


def get_access_token(client_id: str, client_secret: str) -> str | None:
    """Get a valid access token using cached credentials.

    Silently refreshes the token if expired. Does not prompt for login.
    Use authenticate_loopback_flow() first to establish credentials.

    Args:
        client_id: Google Cloud OAuth client ID.
        client_secret: Google Cloud OAuth client secret (needed for refresh).

    Returns:
        Access token string, or None if not authenticated.
    """
    creds = _load_token()

    if not creds:
        return None

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
        except Exception:
            # Refresh failed
            return None

    if creds.valid:
        return creds.token

    return None


def is_authenticated(client_id: str, client_secret: str) -> bool:
    """Check if we have valid cached credentials.

    Attempts to refresh if expired, so this may make a network request.

    Args:
        client_id: Google Cloud OAuth client ID.
        client_secret: Google Cloud OAuth client secret.

    Returns:
        True if valid cached credentials exist.
    """
    return get_access_token(client_id, client_secret) is not None
