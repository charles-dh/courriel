# PRD: Configuration and Authentication

## Overview

Implement the `courriel config` command group to manage application configuration and Microsoft 365 authentication.

## Configuration Structure

```
~/.config/courriel/
├── config.toml          # Account settings, defaults
└── credentials/
    └── ms365_cache.json # MSAL token cache
```

## Config File Format

```toml
[defaults]
max_messages = 100
days = 30

[accounts.work]
provider = "ms365"
tenant_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
client_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
mail_dir = "~/Mail/Work"

[accounts.personal]
provider = "ms365"
tenant_id = "..."
client_id = "..."
mail_dir = "~/Mail/Personal"
```

## Authentication

**Flow:** Device Code Flow (user gets code, opens browser, authenticates)

**Token Storage:** File-based MSAL `SerializableTokenCache` at `~/.config/courriel/credentials/ms365_cache.json`

**Client Secret:** Read from environment variable `COURRIEL_MS365_CLIENT_SECRET`, fallback to `client_secret` in account config

**Scopes:** `User.Read`, `Mail.ReadWrite`, `offline_access`

## Commands

### `courriel config init`

Creates default config directory and empty `config.toml` with template.

### `courriel config auth [--account NAME]`

Authenticates with Microsoft 365 using Device Code Flow:
1. Load account config (or prompt for tenant_id/client_id if not configured)
2. Display device code and verification URL
3. Wait for user to complete browser authentication
4. Store tokens in MSAL cache

### `courriel config show [--account NAME]`

Display current configuration (redact secrets).

### `courriel config set KEY VALUE`

Set a configuration value. Supports dot notation: `defaults.max_messages`, `accounts.work.tenant_id`.

## Multi-Account

- Config structure supports multiple accounts
- First iteration: implement single account (default account)
- Account selection via `--account` flag on commands

## Dependencies

- `msal` - Microsoft authentication
- `tomllib` (stdlib) - Read TOML
- `tomli-w` - Write TOML (stdlib only reads)
