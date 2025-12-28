# Implementation Plan: Sync Command

## Context

Courriel is a CLI tool for syncing Gmail to local Maildir storage. The `sync` command is the core feature that enables offline access and local search via `notmuch`.

**Key decisions from PRD:**

- Gmail-first (MS365 deprioritized due to admin consent requirements)
- Use Gmail History API for incremental sync (no custom deduplication)
- Default labels: INBOX, SENT, DRAFT
- Default limit: 100 messages per label
- Store only `historyId` for sync state

**Reference:** [PRD: Sync Command](../PRD/prd-sync.md)

---

## Developer Instructions

**This is a living document.** The developer implementing this feature must:

1. **Update progress as you work:**
   - Mark checkboxes `[x]` as you complete each step
   - Update the Progress Tracking table with current status
   - Add completion date in the Notes column

2. **Document issues encountered:**
   - Add non-blocking issues to the "Issues Encountered" section below
   - Include workarounds if applicable
   - Flag blocking issues immediately to the team

3. **Commit after each milestone:**
   - Run `uv run ruff check . && uv run ruff format .` before committing
   - Run `uv run pytest` to ensure all tests pass
   - Commit with message: `feat(sync): Complete milestone N - <description>`
   - Example: `feat(sync): Complete milestone 1 - Gmail API client`

4. **Keep tests green:**
   - Each milestone includes its own test suite
   - Do not proceed to next milestone until current tests pass
   - If a test is flaky or needs adjustment, document why

---

## Milestones

### Milestone 1: Gmail API Client

**Goal:** Create a Gmail client wrapper that handles API calls and authentication.

**Files:** `courriel/sync/gmail.py`, `tests/test_gmail_client.py`

#### Step 1.1: Service Initialization

- [ ] Create `GmailClient` class in `sync/gmail.py`
- [ ] Add `__init__(self, credentials)` that builds Gmail API service
- [ ] Use `googleapiclient.discovery.build("gmail", "v1", credentials=creds)`
- [ ] Add helper to get credentials from `auth/gmail.py`

#### Step 1.2: List Labels

- [ ] Implement `list_labels() -> list[dict]`
- [ ] API: `service.users().labels().list(userId="me").execute()`
- [ ] Return list of `{id, name, type}` dicts

#### Step 1.3: List Messages

- [ ] Implement `list_messages(label_id: str, query: str | None, max_results: int) -> list[str]`
- [ ] API: `service.users().messages().list(userId="me", labelIds=[label_id], q=query, maxResults=max_results).execute()`
- [ ] Handle pagination via `nextPageToken`
- [ ] Return list of message IDs

#### Step 1.4: Get Message

- [ ] Implement `get_message(message_id: str) -> dict`
- [ ] API: `service.users().messages().get(userId="me", id=message_id, format="raw").execute()`
- [ ] Return dict with `id`, `threadId`, `labelIds`, `historyId`, `raw` (base64url RFC 2822)
- [ ] Decode `raw` from base64url to bytes

#### Step 1.5: List History (for incremental sync)

- [ ] Implement `list_history(start_history_id: str, label_id: str | None) -> dict`
- [ ] API: `service.users().history().list(userId="me", startHistoryId=start_history_id, labelId=label_id).execute()`
- [ ] Handle pagination
- [ ] Return `{history: [...], historyId: str}`

#### Step 1.6: Unit Tests

- [ ] Create `tests/test_gmail_client.py`
- [ ] Mock `googleapiclient` responses using `unittest.mock`
- [ ] Test `list_labels()` returns parsed labels
- [ ] Test `list_messages()` handles pagination
- [ ] Test `get_message()` decodes base64url correctly
- [ ] Test `list_history()` returns change records

**Acceptance:**

- All tests pass with `uv run pytest tests/test_gmail_client.py`
- Can authenticate and list messages from INBOX (manual test)

---

### Milestone 2: Maildir Storage

**Goal:** Write emails to local Maildir format compatible with `notmuch`.

**Files:** `courriel/storage/maildir.py`, `tests/test_maildir.py`

#### Step 2.1: Folder Structure

- [ ] Create `MaildirStorage` class in `storage/maildir.py`
- [ ] Add `__init__(self, base_path: Path)` - base Maildir directory (e.g., `~/Mail/Personal`)
- [ ] Implement `ensure_folder(folder_name: str)` - creates `cur/`, `new/`, `tmp/` subdirs
- [ ] Handle nested folders (e.g., `Labels/MyLabel`)

#### Step 2.2: Label to Folder Mapping

- [ ] Define `LABEL_FOLDER_MAP` constant:
  ```python
  LABEL_FOLDER_MAP = {
      "INBOX": "INBOX",
      "SENT": "Sent",
      "DRAFT": "Drafts",
      "TRASH": "Trash",
      "SPAM": "Spam",
  }
  ```
- [ ] Implement `label_to_folder(label_id: str) -> str`
- [ ] User labels map to `Labels/<name>`
- [ ] Priority for multi-label: INBOX > SENT > DRAFT > first custom label

#### Step 2.3: Gmail Labels to Maildir Flags

- [ ] Define flag mapping:
  ```python
  # Gmail label -> Maildir flag
  # UNREAD absent -> "S" (Seen)
  # STARRED -> "F" (Flagged)
  # DRAFT -> "D" (Draft)
  # TRASH -> "T" (Trashed)
  ```
- [ ] Implement `labels_to_flags(label_ids: list[str]) -> str`
- [ ] Flags are alphabetically sorted (e.g., `"FS"` not `"SF"`)

#### Step 2.4: Message Filename Generation

- [ ] Implement `generate_filename(message_id: str, flags: str) -> str`
- [ ] Format: `<timestamp>.<message_id>.<hostname>:2,<flags>`
- [ ] Use `time.time()` for timestamp, `socket.gethostname()` for hostname
- [ ] Example: `1704067200.abc123def456.myhost:2,S`

#### Step 2.5: Write Message

- [ ] Implement `write_message(folder: str, message_bytes: bytes, label_ids: list[str]) -> Path`
- [ ] Determine target folder from labels using priority rules
- [ ] Generate flags from labels
- [ ] Write to `tmp/` first, then move to `new/` or `cur/` (atomic)
- [ ] Messages with UNREAD label go to `new/`, others to `cur/`
- [ ] Return path to written file

#### Step 2.6: Check Message Exists

- [ ] Implement `message_exists(message_id: str) -> bool`
- [ ] Search all folders for filename containing message_id
- [ ] Used to skip already-synced messages during full sync

#### Step 2.7: Unit Tests

- [ ] Create `tests/test_maildir.py`
- [ ] Use `tmp_path` fixture for isolated filesystem tests
- [ ] Test `ensure_folder()` creates correct structure
- [ ] Test `label_to_folder()` mappings (system + user labels)
- [ ] Test `labels_to_flags()` conversion and sorting
- [ ] Test `generate_filename()` format
- [ ] Test `write_message()` writes to correct location
- [ ] Test `write_message()` atomic write (tmp → cur/new)
- [ ] Test `message_exists()` finds existing messages

**Acceptance:**

- All tests pass with `uv run pytest tests/test_maildir.py`
- Written messages readable by `notmuch new` (manual test)

---

### Milestone 3: Sync Engine (Full Sync)

**Goal:** Orchestrate full sync from Gmail to Maildir.

**Files:** `courriel/sync/engine.py`, `courriel/sync/state.py`, `tests/test_sync_engine.py`

#### Step 3.1: Sync State Management

- [ ] Create `sync/state.py` with `SyncState` class
- [ ] Add `__init__(self, account_name: str)` - loads state from `~/.config/courriel/sync-state/<account>.json`
- [ ] Implement `load() -> dict | None` - returns `{history_id, last_sync, synced_labels}` or None if not exists
- [ ] Implement `save(history_id: str, synced_labels: list[str])` - persists state to disk
- [ ] Implement `get_history_id() -> str | None`
- [ ] Create sync-state directory if not exists with restricted permissions (700)

#### Step 3.2: SyncEngine Initialization

- [ ] Create `sync/engine.py` with `SyncEngine` class
- [ ] Add `__init__(self, gmail_client: GmailClient, maildir: MaildirStorage, state: SyncState)`
- [ ] Store references to dependencies

#### Step 3.3: Build Date Query

- [ ] Implement `_build_query(since: date | None, days: int | None) -> str | None`
- [ ] Gmail query format: `after:YYYY/MM/DD`
- [ ] If `days` provided, calculate date from today
- [ ] Return None if no date filter

#### Step 3.4: Full Sync Implementation

- [ ] Implement `full_sync(labels: list[str], max_messages: int, query: str | None) -> SyncResult`
- [ ] For each label:
  - Call `gmail_client.list_messages(label_id, query, max_messages)`
  - For each message ID, check `maildir.message_exists(message_id)`
  - If not exists, call `gmail_client.get_message(message_id)`
  - Call `maildir.write_message(folder, raw_bytes, label_ids)`
  - Track highest `historyId` seen
- [ ] After all labels synced, call `state.save(history_id, labels)`
- [ ] Return `SyncResult` dataclass with counts (downloaded, skipped, errors)

#### Step 3.5: Progress Callback

- [ ] Add optional `progress_callback: Callable[[str, int, int], None]` parameter
- [ ] Call with `(label, current, total)` during sync
- [ ] Allows CLI to display progress bar

#### Step 3.6: Unit Tests

- [ ] Create `tests/test_sync_engine.py`
- [ ] Mock `GmailClient` and use real `MaildirStorage` with `tmp_path`
- [ ] Test `SyncState` load/save round-trip
- [ ] Test `_build_query()` with various date inputs
- [ ] Test `full_sync()` writes messages to correct folders
- [ ] Test `full_sync()` skips existing messages
- [ ] Test `full_sync()` saves historyId after completion

**Acceptance:**

- All tests pass with `uv run pytest tests/test_sync_engine.py`
- Can sync INBOX to local Maildir (manual test)
- Messages readable with `cat` or `notmuch`

---

### Milestone 4: Incremental Sync

**Goal:** Use History API to sync only changes since last sync.

**Files:** `courriel/sync/engine.py` (extend), `tests/test_incremental_sync.py`

#### Step 4.1: Detect Sync Mode

- [ ] Implement `sync(labels, max_messages, query) -> SyncResult` as main entry point
- [ ] Check `state.get_history_id()`
- [ ] If None → call `full_sync()`
- [ ] If exists → call `incremental_sync()`

#### Step 4.2: Incremental Sync Implementation

- [ ] Implement `incremental_sync(labels: list[str]) -> SyncResult`
- [ ] Call `gmail_client.list_history(start_history_id, label_id)` for each label
- [ ] Handle `HttpError` with status 404 → fall back to `full_sync()`

#### Step 4.3: Process History Records

- [ ] For each history record, check `messagesAdded`:
  - Extract message IDs from `messagesAdded[].message.id`
  - Fetch full message with `gmail_client.get_message()`
  - Write to Maildir with `maildir.write_message()`
- [ ] Ignore `messagesDeleted` for v1 (preserve local copies)
- [ ] Ignore `labelsAdded`/`labelsRemoved` for v1 (flags not updated)

#### Step 4.4: Update State

- [ ] After processing all history, get new `historyId` from response
- [ ] Call `state.save(new_history_id, labels)`

#### Step 4.5: Unit Tests

- [ ] Create `tests/test_incremental_sync.py`
- [ ] Test `sync()` calls `full_sync()` when no historyId
- [ ] Test `sync()` calls `incremental_sync()` when historyId exists
- [ ] Test `incremental_sync()` only fetches new messages
- [ ] Test fallback to full sync on HTTP 404
- [ ] Test historyId updated after incremental sync

**Acceptance:**

- All tests pass with `uv run pytest tests/test_incremental_sync.py`
- Second sync only downloads new messages (manual test)
- Falls back to full sync when historyId expires

---

### Milestone 5: CLI Integration

**Goal:** Wire sync engine to CLI command with user-friendly output.

**Files:** `courriel/cli/commands/sync.py`, `tests/test_cli_sync.py`

#### Step 5.1: Load Account Configuration

- [ ] Import config loading from `courriel/config/`
- [ ] Get account settings: `provider`, `client_id`, `mail_dir`
- [ ] Validate provider is "gmail" (MS365 not yet supported)
- [ ] Expand `mail_dir` path (handle `~`)

#### Step 5.2: Initialize Dependencies

- [ ] Get credentials using `auth/gmail.py` functions
- [ ] If not authenticated, prompt user to run `courriel config auth` first
- [ ] Create `GmailClient`, `MaildirStorage`, `SyncState` instances
- [ ] Create `SyncEngine` with dependencies

#### Step 5.3: Parse CLI Options

- [ ] `--folder` → single label to sync
- [ ] `--all` → use default labels from config (or `["INBOX", "SENT", "DRAFT"]`)
- [ ] `--max-messages` → override default (100)
- [ ] `--since` → parse as `YYYY-MM-DD` date
- [ ] `--days` → integer, mutually exclusive with `--since`
- [ ] Validate: must specify `--folder` or `--all`

#### Step 5.4: Progress Display

- [ ] Use `typer.echo()` for simple output (or Rich if already a dependency)
- [ ] Display: `Syncing <label>... <current>/<total>`
- [ ] Pass progress callback to `SyncEngine.sync()`

#### Step 5.5: Result Summary

- [ ] After sync completes, display summary:
  ```
  Sync complete:
    - 25 messages downloaded
    - 5 already synced (skipped)
    - 0 errors
  ```
- [ ] If errors, list them with message IDs

#### Step 5.6: Error Handling

- [ ] Catch `HttpError` from Google API → user-friendly message
- [ ] Catch auth errors → suggest `courriel config auth`
- [ ] Catch network errors → suggest checking connection
- [ ] Use `typer.Exit(code=1)` for failures

#### Step 5.7: Unit Tests

- [ ] Create `tests/test_cli_sync.py`
- [ ] Use `typer.testing.CliRunner` for CLI tests
- [ ] Test `--folder INBOX` invokes sync with correct label
- [ ] Test `--all` uses default labels
- [ ] Test `--max-messages` override
- [ ] Test `--since` and `--days` parsing
- [ ] Test error handling displays user-friendly messages
- [ ] Mock `SyncEngine` to avoid real API calls

**Acceptance:**

- All tests pass with `uv run pytest tests/test_cli_sync.py`
- `courriel sync --folder INBOX` works end-to-end
- `courriel sync --all --days 30` syncs default labels
- Clear error messages for common failures

---

### Milestone 6: Documentation

**Goal:** Document sync usage and update project docs.

**Scope:**

- [ ] Update README with sync command usage examples
- [ ] Document configuration options for sync
- [ ] Add troubleshooting section for common errors (auth, network, quota)
- [ ] Update CLI help text with clear descriptions

**Acceptance:**

- README includes working sync examples
- `courriel sync --help` provides clear guidance

---

## Progress Tracking

| Milestone           | Status      | Notes                  |
| ------------------- | ----------- | ---------------------- |
| 1. Gmail API Client | Not started | 6 steps + tests        |
| 2. Maildir Storage  | Not started | 7 steps + tests        |
| 3. Full Sync        | Not started | 6 steps + tests        |
| 4. Incremental Sync | Not started | 5 steps + tests        |
| 5. CLI Integration  | Not started | 7 steps + tests        |
| 6. Documentation    | Not started | 4 steps, no code tests |

---

## Issues Encountered

_Document non-blocking issues here as they arise during implementation._

| Issue | Workaround | Status | Notes |
| ----- | ---------- | ------ | ----- |
| _None yet_ | | | |

---

## Decisions Made

1. **Message deletion:** Ignore for v1, preserve local copies. Revisit in v2.

2. **Label changes:** Update flags only for v1, don't move between folders.

3. **Duplicate messages:** Pick primary label (INBOX > SENT > DRAFT > first custom). Don't store duplicates.

---

## Dependencies

- `google-api-python-client` - Gmail API client (already in project)
- `google-auth-oauthlib` - OAuth flow (already in project)
- Existing `auth/gmail.py` - Token management (implemented)
- Existing `config/` module - Configuration loading (implemented)
