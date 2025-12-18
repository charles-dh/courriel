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

**First iteration:** Microsoft365 only with local operations.

**Future:** Gmail support via Gmail API.

## Dependencies

- **Package management:** `uv`
- **Authentication:** `msal` (Microsoft identity platform)
- **API clients:** `requests`
- **CLI framework:** `typer`
- **Local search:** `notmuch`
- **APIs:** Microsoft Graph API, Gmail API (future)

## Microsoft 365 Setup

1. Register an application in [Microsoft Entra ID](https://portal.azure.com/#view/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/~/RegisteredApps)
2. Configure API permissions:
   - `User.Read`
   - `Mail.ReadWrite`
   - `offline_access`
3. Grant admin consent for the permissions
4. Create a client secret
5. Save the **Application (client) ID**, **Directory (tenant) ID**, and **client secret** for configuration

## Architecture

**Sync:** Emulates `mbsync` behavior using Microsoft Graph API with configurable message limits and incremental updates.

**Local Search:** Wrapper around `notmuch` for fast, indexed searches in Maildir.

**Remote Search:** Direct API queries for server-side search capabilities.

**Drafting:** API-based email composition and replies (no SMTP sending).

## Directory Structure:

courriel/  
 ├── auth/ # Microsoft365 authentication  
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
