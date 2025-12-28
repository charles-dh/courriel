# PRD: Gmail Authentication

## Overview

Implement Gmail authentication using OAuth 2.0 Installed Application flow to support Gmail accounts alongside MS365.

## Authentication Flow

**Flow:** Installed Application Flow with Loopback Redirect

**Process:**
1. User runs `courriel config auth --account ACCOUNT_NAME`
2. CLI starts temporary local server on `http://localhost:8080`
3. Opens browser to Google OAuth consent page
4. User authenticates with Google and grants permissions
5. Google redirects to `http://localhost:8080` with authorization code
6. CLI captures code, exchanges for tokens
7. Store tokens in `~/.config/courriel/credentials/gmail_token.json`

**Token Storage:** JSON file at `~/.config/courriel/credentials/gmail_token.json`

**Client Secret:** Read from environment variable `COURRIEL_GMAIL_CLIENT_SECRET`, fallback to `client_secret` in account config

**Scopes:**
- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/gmail.modify`
- `https://www.googleapis.com/auth/gmail.compose`

## Config File Format

```toml
[accounts.personal]
provider = "gmail"
client_id = "xxxxx.apps.googleusercontent.com"
client_secret = "xxxxx"  # Optional, prefer env var
mail_dir = "~/Mail/Personal"

[accounts.work]
provider = "ms365"
tenant_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
client_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
mail_dir = "~/Mail/Work"
```

## Google Cloud Console Setup

1. Create project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable Gmail API
3. Configure OAuth consent screen (external type for personal accounts)
4. Create OAuth 2.0 credentials:
   - Application type: **Desktop app**
   - Download credentials or save client ID/secret
5. Add authorized redirect URI: `http://localhost:8080` (for development/testing)

## Token Management

**Token Structure (gmail_token.json):**
```json
{
  "token": "ya29.xxx...",
  "refresh_token": "1//xxx...",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "xxxxx.apps.googleusercontent.com",
  "client_secret": "xxxxx",
  "scopes": ["https://www.googleapis.com/auth/gmail.readonly", ...],
  "expiry": "2025-12-19T10:30:00.000000Z"
}
```

**Token Refresh:** Automatically refresh access token using refresh token when expired (tokens expire after ~1 hour)

## Authentication Command

The existing `courriel config auth --account NAME` command should detect provider type from config and use appropriate auth flow:

- If `provider = "ms365"`: Use MSAL Device Code Flow
- If `provider = "gmail"`: Use OAuth 2.0 Installed App Flow

## Dependencies

- `google-auth-oauthlib` - OAuth 2.0 flow implementation
- `google-auth-httplib2` - HTTP transport for google-auth
- `google-api-python-client` - Gmail API client

## Implementation Notes

- Use `flow.run_local_server(port=8080)` from `google_auth_oauthlib.flow` for loopback flow
- Store credentials using `google.oauth2.credentials.Credentials.to_json()`
- Load credentials using `google.oauth2.credentials.Credentials.from_authorized_user_file()`
- Handle token refresh automatically via `google-auth` library
