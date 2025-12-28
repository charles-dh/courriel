# PRD: Sync Command

## Overview

The `sync` command synchronizes emails from Gmail to local Maildir storage. It enables offline access, local search via `notmuch`, and integration with other email tools.

## Goals

1. **Reliable synchronization** - Fetch emails from Gmail API and store locally in Maildir format
2. **Incremental sync** - Use Gmail History API to only download new/changed messages
3. **Configurable limits** - Control sync scope by label, date range, or message count
4. **Idempotent operation** - Running sync multiple times produces the same result

## Non-Goals (for v1)

- Two-way sync (local changes reflected remotely)
- Attachment-only sync or attachment exclusion
- Real-time push notifications
- Microsoft 365 support (future)

## CLI Interface

```bash
courriel sync [OPTIONS]
```

### Options

| Option | Type | Description |
|--------|------|-------------|
| `--folder TEXT` | string | Sync specific label (e.g., "INBOX", "SENT") |
| `--all` | flag | Sync all default labels |
| `--max-messages INT` | integer | Maximum messages to sync per label (default: 100) |
| `--since DATE` | date | Sync messages after date (YYYY-MM-DD) |
| `--days INT` | integer | Sync messages from last N days |

### Examples

```bash
# Sync inbox with default limits
courriel sync --folder INBOX

# Sync default labels, last 30 days
courriel sync --all --days 30

# Sync inbox, max 50 messages
courriel sync --folder INBOX --max-messages 50

# Sync messages since specific date
courriel sync --folder INBOX --since 2024-01-01
```

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI Layer                                │
│                 (cli/commands/sync.py)                       │
│   Parses options, loads config, orchestrates sync            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Sync Engine                               │
│                   (sync/engine.py)                           │
│   Coordinates fetching from API and writing to storage       │
│   Manages sync state (historyId) for incremental sync        │
└─────────────────────────────────────────────────────────────┘
                    │                   │
                    ▼                   ▼
┌───────────────────────────┐  ┌───────────────────────────────┐
│      Gmail Client         │  │      Maildir Storage          │
│    (sync/gmail.py)        │  │    (storage/maildir.py)       │
│  - List messages          │  │  - Write messages             │
│  - Get message (raw)      │  │  - Create folder structure    │
│  - List history           │  │  - Map labels to folders      │
│  - List labels            │  │                               │
└───────────────────────────┘  └───────────────────────────────┘
                    │
                    ▼
┌───────────────────────────┐
│      Auth Module          │
│    (auth/gmail.py)        │
│  - Get access token       │
│  - Handle refresh         │
└───────────────────────────┘
```

### Data Flow

**Initial Sync (Full):**
1. CLI parses arguments, loads account config
2. Sync Engine calls Gmail Client to list messages with filters
3. For each message ID, fetch full content (`format=RAW`)
4. Maildir Storage writes message to appropriate folder
5. Store `historyId` from most recent message for future syncs

**Subsequent Sync (Incremental):**
1. Load stored `historyId` from sync state
2. Call `history.list` with `startHistoryId`
3. Process changes: `messagesAdded`, `messagesDeleted`, `labelsAdded`, `labelsRemoved`
4. Fetch full content only for new messages
5. Update stored `historyId`

**Fallback:** If `history.list` returns HTTP 404 (historyId expired), perform full sync.

## Gmail API Usage

### List Messages (Full Sync)

```
GET /gmail/v1/users/me/messages
```

| Parameter | Description |
|-----------|-------------|
| `q` | Gmail search query (e.g., `after:2024/01/01`) |
| `labelIds` | Filter by label ID |
| `maxResults` | Page size (default: 100, max: 500) |
| `pageToken` | Pagination token |

### Get Message

```
GET /gmail/v1/users/me/messages/{id}
```

| Parameter | Description |
|-----------|-------------|
| `format` | `RAW` - base64url-encoded RFC 2822 message |
|          | `FULL` - parsed structure with payload/parts |
|          | `METADATA` - headers only |
|          | `MINIMAL` - id, threadId, labelIds only |

We use `format=RAW` to get the complete RFC 2822 message for Maildir storage.

### History List (Incremental Sync)

```
GET /gmail/v1/users/me/history
```

| Parameter | Description |
|-----------|-------------|
| `startHistoryId` | Required. Returns changes after this ID |
| `maxResults` | Default: 100, max: 500 |
| `labelId` | Filter to specific label |
| `historyTypes` | Filter: `messageAdded`, `messageDeleted`, `labelAdded`, `labelRemoved` |

**Response fields:**
- `history[]` - List of change records
- `historyId` - Current history ID (store this for next sync)
- `nextPageToken` - For pagination

**Note:** historyId typically valid for ~1 week. HTTP 404 means expired → full sync required.

### List Labels

```
GET /gmail/v1/users/me/labels
```

Returns all labels with `id`, `name`, `type` (system/user).

## Gmail Labels

### System Labels (Reserved)

Cannot be created/deleted. Some can be applied/removed from messages.

| Label ID | Description | Sync by default |
|----------|-------------|-----------------|
| `INBOX` | Inbox | Yes |
| `SENT` | Sent mail | Yes |
| `DRAFT` | Drafts | Yes |
| `STARRED` | Starred/flagged | No |
| `IMPORTANT` | Important | No |
| `UNREAD` | Unread (virtual) | No |
| `SPAM` | Spam | No |
| `TRASH` | Trash | No |
| `CATEGORY_PERSONAL` | Category tab | No |
| `CATEGORY_SOCIAL` | Category tab | No |
| `CATEGORY_PROMOTIONS` | Category tab | No |
| `CATEGORY_UPDATES` | Category tab | No |
| `CATEGORY_FORUMS` | Category tab | No |

### User Labels

Custom labels created by user. Synced if `--all` is specified.

### Default Sync Labels

When no `--folder` specified, sync: `INBOX`, `SENT`, `DRAFT`

## Maildir Format

### Directory Structure

```
~/Mail/<account>/
├── INBOX/
│   ├── cur/          # Read messages
│   ├── new/          # Unread messages
│   └── tmp/          # Messages being delivered
├── Sent/
│   ├── cur/
│   ├── new/
│   └── tmp/
├── Drafts/
└── Labels/
    └── <user-label>/
```

### Label to Folder Mapping

| Gmail Label | Maildir Folder |
|-------------|----------------|
| `INBOX` | `INBOX/` |
| `SENT` | `Sent/` |
| `DRAFT` | `Drafts/` |
| `TRASH` | `Trash/` |
| `SPAM` | `Spam/` |
| `STARRED` | (flag, not folder) |
| User labels | `Labels/<name>/` |

### Message Naming

Maildir filenames: `<timestamp>.<unique-id>.<hostname>:2,<flags>`

Example: `1704067200.abc123def.localhost:2,S`

### Flags

| Flag | Meaning | Gmail Equivalent |
|------|---------|------------------|
| S | Seen (read) | Not in UNREAD label |
| R | Replied | Has REPLIED label (if available) |
| F | Flagged | STARRED label |
| T | Trashed | TRASH label |
| D | Draft | DRAFT label |

## Sync State

Store sync state per account:

**Location:** `~/.config/courriel/sync-state/<account>.json`

```json
{
  "history_id": "12345678",
  "last_sync": "2024-01-15T10:30:00Z",
  "synced_labels": ["INBOX", "SENT", "DRAFT"]
}
```

Minimal state - just the historyId. Gmail's History API handles deduplication.

## Configuration

```toml
[defaults]
max_messages = 100
days = 90
sync_labels = ["INBOX", "SENT", "DRAFT"]

[accounts.personal]
provider = "gmail"
client_id = "xxx.apps.googleusercontent.com"
mail_dir = "~/Mail/Personal"
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Network error | Retry with exponential backoff (3 attempts), then fail |
| Auth expired | Attempt token refresh, prompt re-auth if needed |
| History ID expired (404) | Fall back to full sync |
| Rate limit (429) | Pause, respect Retry-After header |
| Malformed message | Log warning, skip message, continue |
| Disk full | Fail immediately with clear error |

## Progress Reporting

```
Syncing personal account...

INBOX:
  Checking for changes... 15 new messages
  Downloading: [████████████░░░░░░░░] 8/15

Sent:
  Checking for changes... 3 new messages
  Downloading: [████████████████████] 3/3

Sync complete:
  - 18 messages downloaded
  - 0 errors
  - Next sync will be incremental
```

## Success Criteria

1. Full sync downloads messages from INBOX to local Maildir
2. Incremental sync only fetches new messages using History API
3. Messages readable with `notmuch` and standard Maildir tools
4. Respects `--max-messages`, `--days`, `--since` filters
5. Handles pagination for large mailboxes
6. Falls back to full sync when historyId expires
7. Clear error messages for auth, network, and API failures

## Future Enhancements

- Microsoft 365 provider support
- Parallel message downloads (batch API)
- Push notifications via Gmail watch API
- Selective attachment handling
- Two-way sync (read status, stars)
