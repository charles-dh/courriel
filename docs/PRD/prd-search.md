# PRD: Search Command

## Overview

The `search` command provides unified email search across local Maildir storage (via notmuch) and remote providers (Gmail, MS365). Local search is the default; remote search is available as an option.

## Goals

1. **Local-first search** - Fast, indexed search using notmuch
2. **Unified interface** - Same command works for local and remote search
3. **Multi-account** - Search across all accounts by default
4. **Extensible** - Interface supports future remote search and advanced features

## Non-Goals (v1)

- Remote search (Gmail API, MS365 Graph API)
- Query syntax translation between providers
- Result deduplication across accounts
- Full-text body search on remote (provider limitations)

## CLI Interface

```bash
courriel search <query> [OPTIONS]
```

### Arguments

| Argument | Type   | Description                                                       |
| -------- | ------ | ----------------------------------------------------------------- |
| `query`  | string | Search query (notmuch syntax for local, native syntax for remote) |

### Options

| Option      | Type    | Description                                                               |
| ----------- | ------- | ------------------------------------------------------------------------- |
| `--all`     | flag    | Search all accounts (default behavior, explicit for clarity)              |
| `--account` | string  | Search specific account only                                              |
| `--limit`   | integer | Maximum results to return (default: 50)                                   |
| `--output`  | string  | Output format: `json`, `summary`, `files` (default: `json`, configurable) |
| `--remote`  | flag    | Search remote provider instead of local (v2)                              |

### Examples

```bash
# Search all accounts locally (default)
courriel search "from:alice@example.com"

# Explicitly search all accounts
courriel search "from:alice@example.com" --all

# Search specific account
courriel search "subject:invoice" --account work

# Limit results
courriel search "date:2024.." --limit 20

# Human-readable output
courriel search "tag:unread" --output summary

# Output as file paths (for piping to other tools)
courriel search "tag:unread" --output files
```

## Query Syntax (v1 - Local)

v1 uses notmuch query syntax directly. Users familiar with notmuch get full power; others get a well-documented standard.

### Common Queries

| Query                           | Description                 |
| ------------------------------- | --------------------------- |
| `from:alice@example.com`        | Sender address              |
| `to:bob@example.com`            | Recipient address           |
| `subject:meeting`               | Subject contains word       |
| `date:2024..`                   | Messages from 2024 onwards  |
| `date:..2024-06-01`             | Messages before June 2024   |
| `tag:unread`                    | Unread messages             |
| `tag:flagged`                   | Starred/flagged messages    |
| `folder:INBOX`                  | Messages in specific folder |
| `attachment:pdf`                | Has PDF attachment          |
| `from:alice AND subject:urgent` | Boolean AND                 |
| `from:alice OR from:bob`        | Boolean OR                  |
| `NOT tag:spam`                  | Negation                    |

Full syntax: https://notmuchmail.org/doc/latest/man7/notmuch-search-terms.html

## Output Formats

### JSON (default)

Structured output for agents and scripting. Includes a body snippet (first ~200 chars) for quick content preview:

```json
{
  "query": "from:alice@example.com",
  "total": 4,
  "results": [
    {
      "id": "abc123@example.com",
      "account": "personal",
      "file": "/home/user/Mail/Personal/INBOX/cur/1705312800.abc123.host:2,S",
      "date": "2024-01-15T10:00:00Z",
      "from": "Alice Smith <alice@example.com>",
      "to": ["bob@example.com"],
      "subject": "Re: Project update",
      "snippet": "Thanks for the update! I've reviewed the changes and everything looks good. Let me know if you need...",
      "tags": ["inbox", "replied"]
    },
    {
      "id": "def456@example.com",
      "account": "work",
      "file": "/home/user/Mail/Work/INBOX/cur/1705139200.def456.host:2,S",
      "date": "2024-01-12T14:30:00Z",
      "from": "alice@corp.com",
      "to": ["team@corp.com"],
      "subject": "Q4 Review",
      "snippet": "Please find attached the Q4 review document. Key highlights: revenue up 15%, new customer...",
      "tags": ["inbox", "unread"]
    }
  ]
}
```

### Summary

Human-readable format for terminal use:

```
personal: 3 results
  2024-01-15 alice@example.com    Re: Project update
  2024-01-14 alice@example.com    Project update
  2024-01-10 alice@example.com    Initial proposal

work: 1 result
  2024-01-12 alice@corp.com       Q4 Review
```

### Files

One file path per line, for piping to other tools:

```
/home/user/Mail/Personal/INBOX/cur/1705312800.abc123.host:2,S
/home/user/Mail/Personal/INBOX/cur/1705226400.def456.host:2,S
/home/user/Mail/Work/INBOX/cur/1705139200.ghi789.host:2,S
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI Layer                              │
│                 (cli/commands/search.py)                    │
│   Parses query, selects accounts, formats output            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Search Interface                          │
│                   (search/base.py)                          │
│   Abstract interface for search backends                    │
└─────────────────────────────────────────────────────────────┘
                    │                   │
                    ▼                   ▼ (v2)
┌───────────────────────────┐  ┌───────────────────────────────┐
│    Local Search           │  │    Remote Search              │
│   (search/local.py)       │  │   (search/gmail.py)           │
│   - notmuch wrapper       │  │   (search/ms365.py)           │
│   - Parse results         │  │   - API queries               │
│   - Map to common format  │  │   - Map to common format      │
└───────────────────────────┘  └───────────────────────────────┘
```

### Search Result Model

```python
@dataclass
class SearchResult:
    id: str                    # Message ID (e.g., "abc123@example.com")
    account: str               # Account name
    file: str | None           # Local file path (local search only)
    date: datetime
    from_addr: str             # Full "Name <email>" format
    to_addrs: list[str]
    subject: str
    snippet: str               # Body preview (~200 chars, stripped of HTML/whitespace)
    tags: list[str]            # notmuch tags / Gmail labels
```

### Local Search Flow

1. CLI receives query and options
2. For each account (or specified account):
   - Get `mail_dir` from config
   - Run `notmuch search` with query scoped to that mail_dir
   - Parse output into `SearchResult` objects
3. Aggregate results, apply limit
4. Format output based on `--output` option

## notmuch Integration

### CLI wrapper

Use Python `subprocess` module to wrap notmuch CLI commands.

`notmuch` is already isntalled

```bash
sudo apt intall notmuch
```

**Note**: We don't use notmuch Python bindings because it's a hell to install and maintain.

### Prerequisites

User must have notmuch installed and database initialized:

```bash
# Install notmuch and Python bindings
apt install notmuch
pip install notmuch2

# Initialize database (one-time)
notmuch new
```

### Database Location

notmuch database lives alongside mail:

- `~/Mail/.notmuch/` (single database for all accounts)
- Queries scoped to account via `folder:` prefix

## Configuration

```toml
[defaults]
search_limit = 50
search_output = "json"          # Default output format: json, summary, files

[accounts.personal]
provider = "gmail"
mail_dir = "~/Mail/Personal"
# notmuch scopes searches via folder: prefix based on mail_dir
```

## Error Handling

| Scenario                 | Behavior                                                      |
| ------------------------ | ------------------------------------------------------------- |
| notmuch not installed    | Error: "notmuch not found. Install with: apt install notmuch" |
| Database not initialized | Error: "Run 'notmuch new' to index your mail"                 |
| Invalid query syntax     | Pass through notmuch error message                            |
| No results               | Empty output (not an error)                                   |
| Account not found        | Error: "Account 'foo' not configured"                         |

## Success Criteria (v1)

1. `courriel search "query"` returns JSON results from all configured accounts
2. `--all` explicitly searches all accounts (same as default)
3. `--account` flag filters to specific account
4. `--limit` controls result count
5. `--output` supports json (default), summary, and files formats
6. Default output format configurable via `defaults.search_output`
7. Results include body snippet (~200 chars) for each message and list of attachments
8. Clear error when notmuch/notmuch2 is not available
9. Results include date, from, to, subject, snippet, tags for each message

---

## v2: Remote Search

### Additional Options

| Option       | Description                                 |
| ------------ | ------------------------------------------- |
| `--remote`   | Search remote provider API instead of local |
| `--fallback` | Search local first, remote if no results    |

### Query Translation (v2)

Translate common query patterns to provider-native syntax:

| Courriel         | notmuch        | Gmail              | MS365 (OData)                           |
| ---------------- | -------------- | ------------------ | --------------------------------------- |
| `from:alice@`    | `from:alice@`  | `from:alice@`      | `from/emailAddress/address eq 'alice@'` |
| `subject:test`   | `subject:test` | `subject:test`     | `contains(subject, 'test')`             |
| `date:2024..`    | `date:2024..`  | `after:2024/01/01` | `receivedDateTime ge 2024-01-01`        |
| `has:attachment` | `attachment:*` | `has:attachment`   | `hasAttachments eq true`                |

### Remote Search Limitations

- **Gmail**: Full search syntax, but API may return different results than web UI
- **MS365**: Limited to OData filters, no full-text body search via API
- **Rate limits**: Both providers have API quotas

### Multi-Account Merge (v2)

When searching multiple accounts:

1. Run searches in parallel
2. Merge results by date (newest first)
3. Indicate source account in output
4. No deduplication (same message in multiple accounts shown separately)

### Fallback Mode (v2)

```bash
courriel search "from:alice" --fallback
```

1. Search local first
2. If zero results AND remote available, search remote
3. Show indicator: "No local results, searching remote..."
