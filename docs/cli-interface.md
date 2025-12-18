# CLI Interface Design

This document outlines the command-line interface for `courriel`.

## Command Structure

```
courriel [COMMAND] [OPTIONS]
```

## Core Commands

### `sync`
Synchronize emails between remote account and local Maildir.

```bash
courriel sync [OPTIONS]
```

**Key options:**
- `--folder TEXT` - Sync specific folder (e.g., "Inbox", "Sent")
- `--all` - Sync all folders
- `--max-messages INT` - Maximum messages to sync per folder
- `--since DATE` - Sync messages after date (ISO format: YYYY-MM-DD)
- `--days INT` - Sync messages from last N days

**Examples:**
```bash
courriel sync --folder Inbox --max-messages 100
courriel sync --all --days 30
courriel sync --since 2024-01-01
```

---

### `read`
Display email message(s).

```bash
courriel read <MESSAGE-ID> [OPTIONS]
```

**Key options:**
- `--format TEXT` - Output format: `text` (default), `json`, `raw`, `headers`
- `--no-attachments` - Don't show attachment info
- `--save-attachments PATH` - Save attachments to directory

**Examples:**
```bash
courriel read <message-id>
courriel read <message-id> --format json
courriel read <message-id> --save-attachments ~/Downloads
```

---

### `search`
Search emails locally or remotely.

```bash
courriel search [QUERY] [OPTIONS]
```

**Key options:**
- `--local` - Search local Maildir (default)
- `--remote` - Search remote account via API
- `--from TEXT` - Filter by sender
- `--to TEXT` - Filter by recipient
- `--subject TEXT` - Filter by subject
- `--body TEXT` - Search in email body
- `--folder TEXT` - Limit to specific folder
- `--since DATE` / `--until DATE` - Date range
- `--format TEXT` - Output format: `summary` (default), `json`, `ids`

**Examples:**
```bash
courriel search --from "boss@company.com" --since 2024-01-01
courriel search --subject "invoice" --local
courriel search --remote --body "meeting notes"
courriel search --from "alerts@" --format json
```

**Note:** For power users familiar with notmuch, we may support notmuch-style query syntax in the future (e.g., `courriel search "from:boss AND subject:invoice"`).

---

### `draft`
Create or reply to email drafts.

```bash
courriel draft [OPTIONS]
```

**Key options:**
- `--to TEXT` - Recipient(s)
- `--subject TEXT` - Email subject
- `--body TEXT` - Email body (or read from stdin)
- `--reply-to ID` - Reply to message ID
- `--attach FILE` - Attach file(s)

**Examples:**
```bash
courriel draft --to "colleague@company.com" --subject "Quick question"
courriel draft --reply-to <message-id> --body "Thanks for the update"
echo "Email body" | courriel draft --to "user@example.com" --subject "Test"
```

---

### `list`
List folders or messages.

```bash
courriel list [folders|messages] [OPTIONS]
```

**Key options:**
- `--remote` - List from remote account
- `--local` - List from local Maildir (default)
- `--folder TEXT` - List messages in specific folder

**Examples:**
```bash
courriel list folders
courriel list messages --folder Inbox
courriel list folders --remote
```

---

### `config`
Manage configuration and authentication.

```bash
courriel config [SUBCOMMAND]
```

**Subcommands:**
- `init` - Initialize configuration
- `auth` - Authenticate with Microsoft365
- `show` - Display current configuration
- `set KEY VALUE` - Set configuration value

**Examples:**
```bash
courriel config init
courriel config auth
courriel config set maildir_path ~/Mail
courriel config show
```

---

## Global Options

- `--help` - Show help message
- `--version` - Show version
- `--config FILE` - Use alternate config file
- `--verbose` / `-v` - Verbose output
- `--quiet` / `-q` - Minimal output

---

## Configuration File

Default location: `~/.config/courriel/config.toml`

```toml
[microsoft365]
client_id = "your-client-id"
tenant_id = "your-tenant-id"
client_secret = "your-client-secret"

[storage]
maildir_path = "~/Mail"
max_messages_per_folder = 1000
max_total_messages = 10000

[sync]
default_folders = ["Inbox", "Sent", "Drafts"]
default_days = 90
```

---

## Notes

- Authentication tokens are stored securely in system keyring
- Message IDs are based on email headers (Message-ID)
- Drafts are created on the server, not sent
- Local search requires `notmuch` database initialization
