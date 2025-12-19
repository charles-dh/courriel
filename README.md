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

Supports both Microsoft 365 and Gmail via their respective APIs with local operations.

## Dependencies

- **Package management:** `uv`
- **Authentication:** `msal` (Microsoft), `google-auth-oauthlib` (Gmail)
- **API clients:** `requests`, `google-api-python-client`
- **CLI framework:** `typer`
- **Local search:** `notmuch`
- **APIs:** Microsoft Graph API, Gmail API

## Microsoft 365 Setup

1. Register an application in [Microsoft Entra ID](https://portal.azure.com/#view/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/~/RegisteredApps)
2. Configure API permissions:
   - `User.Read`
   - `Mail.ReadWrite`
   - `offline_access`
3. Grant admin consent for the permissions
4. Create a client secret
5. Save the **Application (client) ID**, **Directory (tenant) ID**, and **client secret** for configuration

## Gmail Setup

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

## Commands Available:

- courriel sync - with folder, max-messages, since, days, all options
- courriel search - with from, to, subject, body, folder, date range, format
- courriel read - with format, attachments options
- courriel draft - with to, cc, bcc, subject, body, reply-to, attach
- courriel list - with type, remote/local, folder, max-messages
- courriel config - with init, auth, show, set subcommands
- courriel version - displays version
