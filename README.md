# Courriel

A personal CLI tool for managing Microsoft365 and Gmail accounts through local Maildir storage. Designed for personal use, server automation, and AI agent integration.

## Features

**Email Synchronization**

- Sync emails to local Maildir format (`~/Mail`)
- Filter by folder, date range, or message count
- Incremental syncing with configurable limits
- Full attachment support

**Advanced Search**

- Local search via `notmuch` (sender, recipient, subject, body, date)
- Remote search via native APIs
- Support for regex patterns and domain filtering
- Search across cc/bcc fields

**Email Drafting**

- Create and reply to emails via APIs
- No sending capabilities (read and draft only)

## Current Scope

**Gmail-first development.** Microsoft 365 support is planned but deprioritized (requires admin consent for API permissions).

Supports Gmail via the Gmail API with local Maildir operations. MS365 support via Microsoft Graph API will be added later.

## Dependencies

- **Package management:** `uv`
- **Authentication:** `msal` (Microsoft), `google-auth-oauthlib` (Gmail)
- **API clients:** `requests`, `google-api-python-client`
- **CLI framework:** `typer`
- **Local search:** `notmuch`
- **APIs:** Microsoft Graph API, Gmail API

## Gmail Setup (Primary)

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the Gmail API for your project
3. Configure OAuth consent screen:
   - User type: **External** (required for personal Gmail accounts; Internal is only for Google Workspace)
   - App name, user support email, and developer contact email
   - Add scopes: `gmail.readonly`, `gmail.modify`, `gmail.compose`
   - Add your Gmail address as a test user (while app is in "Testing" status)
   - You can keep the app in "Testing" mode for personal use - no need to publish
4. Create OAuth 2.0 credentials:
   - Go to Credentials → Create Credentials → OAuth client ID
   - Application type: **Desktop app**
   - Name it (e.g., "Courriel CLI")
5. Save the **Client ID** and **Client Secret**
6. Set the environment variable: `export COURRIEL_GMAIL_CLIENT_SECRET="your-client-secret"`

**Required Scopes:**
- `https://www.googleapis.com/auth/gmail.readonly` - Read emails for sync and search
- `https://www.googleapis.com/auth/gmail.modify` - Modify labels, mark read/unread
- `https://www.googleapis.com/auth/gmail.compose` - Create drafts

## Microsoft 365 Setup (Future)

> **Note:** MS365 support is deprioritized. The setup below requires admin consent for API permissions.

1. Register an application in [Microsoft Entra ID](https://portal.azure.com/#view/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/~/RegisteredApps)
2. Configure API permissions:
   - `User.Read`
   - `Mail.ReadWrite`
   - `offline_access`
3. Grant admin consent for the permissions
4. Create a client secret
5. Save the **Application (client) ID**, **Directory (tenant) ID**, and **client secret** for configuration

## Architecture

**Sync:** Emulates `mbsync` behavior using provider APIs (Microsoft Graph API, Gmail API) with configurable message limits and incremental updates.

**Local Search:** Wrapper around `notmuch` for fast, indexed searches in Maildir.

**Remote Search:** Direct API queries for server-side search capabilities.

**Drafting:** API-based email composition and replies (no SMTP sending).

**Authentication:** Provider-agnostic interface supporting MS365 (Device Code Flow) and Gmail (OAuth 2.0 loopback flow).

## Directory Structure:

courriel/
 ├── auth/ # Multi-provider authentication (MS365, Gmail)
 ├── cli/ # CLI layer
 │ ├── commands/ # Command implementations
 │ │ ├── sync.py
 │ │ ├── search.py
 │ │ ├── read.py
 │ │ ├── draft.py
 │ │ ├── list.py
 │ │ └── config.py
 │ └── main.py # CLI entry point
 ├── config/ # Configuration management
 ├── draft/ # Email drafting
 ├── search/ # Email search (local/remote)
 ├── storage/ # Maildir operations
 └── sync/ # Email synchronization

## Quick Start

```bash
# Initialize configuration
courriel config init

# Edit config to add your Gmail account
# ~/.config/courriel/config.toml

# Authenticate with Gmail
courriel config auth

# Sync your inbox
courriel sync --folder INBOX

# Sync all default labels
courriel sync --all
```

## Sync Command

The `sync` command downloads emails from Gmail to local Maildir storage.

### Usage

```bash
courriel sync [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--folder TEXT` | Sync a specific label (e.g., INBOX, SENT) |
| `--all` | Sync all default labels (INBOX, SENT, DRAFT) |
| `--max-messages INT` | Maximum messages per label (default: 100) |
| `--since DATE` | Sync messages after date (YYYY-MM-DD) |
| `--days INT` | Sync messages from last N days |
| `--account NAME` | Specify account to sync |
| `--full` | Force full sync (ignore incremental state) |

### Examples

```bash
# Sync inbox with default limits (100 messages)
courriel sync --folder INBOX

# Sync all default labels
courriel sync --all

# Sync inbox, last 30 days only
courriel sync --folder INBOX --days 30

# Sync with custom message limit
courriel sync --folder INBOX --max-messages 500

# Sync messages since a specific date
courriel sync --folder INBOX --since 2024-01-01

# Force full sync (re-download all)
courriel sync --all --full

# Sync a specific account
courriel sync --folder INBOX --account personal
```

### Sync Modes

**Full Sync** (first run or with `--full`):
- Downloads messages up to `--max-messages` limit
- Skips messages already in local storage
- Stores sync state for future incremental syncs

**Incremental Sync** (subsequent runs):
- Uses Gmail History API to fetch only new messages
- Much faster than full sync for regular updates
- Falls back to full sync if history expires (~1 week)

### Maildir Storage

Emails are stored in Maildir format at the path configured in `mail_dir`:

```
~/Mail/Personal/
├── INBOX/
│   ├── cur/    # Read messages
│   ├── new/    # Unread messages
│   └── tmp/    # Temporary (during write)
├── Sent/
├── Drafts/
└── Labels/
    └── <custom-labels>/
```

Compatible with `notmuch`, `mutt`, and other Maildir tools.

## Configuration

Configuration is stored in `~/.config/courriel/config.toml`:

```toml
[defaults]
max_messages = 100          # Default message limit per sync
days = 30                   # Default lookback period
sync_labels = ["INBOX", "SENT", "DRAFT"]  # Labels for --all

[accounts.personal]
provider = "gmail"
client_id = "xxxxx.apps.googleusercontent.com"
mail_dir = "~/Mail/Personal"
```

### Config Commands

```bash
# Initialize config directory and template
courriel config init

# Authenticate with email provider
courriel config auth
courriel config auth --account work

# Show current configuration
courriel config show

# Set a configuration value
courriel config set defaults.max_messages 200
courriel config set accounts.personal.mail_dir ~/Mail/Gmail
```

## Troubleshooting

### Authentication Errors

**"Not authenticated"**
```bash
# Re-authenticate with Gmail
courriel config auth
```

**"Token expired"**
- Tokens auto-refresh, but may expire if unused for extended periods
- Re-run `courriel config auth` to get fresh tokens

### Sync Errors

**"Provider not supported"**
- Currently only Gmail is supported
- MS365 support is planned for a future release

**"No account configured"**
```bash
# Initialize config and add account
courriel config init
# Edit ~/.config/courriel/config.toml
```

**"History ID expired"**
- Gmail History API expires after ~1 week
- Sync automatically falls back to full sync
- Use `--full` to force a fresh full sync

### Common Issues

**Sync is slow**
- First sync downloads all messages (up to limit)
- Subsequent syncs use incremental mode (much faster)
- Reduce `--max-messages` for faster initial sync

**Messages not appearing**
- Check `mail_dir` path in config
- Verify messages exist: `ls ~/Mail/Personal/INBOX/cur/`
- Run `notmuch new` to index for search

## Other Commands

| Command | Description | Status |
|---------|-------------|--------|
| `courriel sync` | Sync emails to Maildir | Implemented |
| `courriel config` | Manage configuration | Implemented |
| `courriel search` | Search emails | Planned |
| `courriel read` | Display messages | Planned |
| `courriel draft` | Create email drafts | Planned |
| `courriel list` | List folders/messages | Planned |
| `courriel version` | Show version | Implemented |
