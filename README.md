# Courriel personal email CLI tool

`courriel` is a personal CLI tool to manage Gmail and Microsoft365 email accounts.
It is intended for my personal use, to schedule background tasks and with AI agents in mind.

## Core features

- sync between Gmail and Microsoft365 email accounts and Maildir locally
  - by folder
  - [N] most recent messages
  - last [N] days/months
  - messages after [date]
- advanced search in remote folders
  - sender email address/name/domain/regex
  - recipient email address/name/domain/regex
  - cc/bcc
  - subject
  - date
  - email body
- advanced search in local Maildir

## Scope

First iteration only supports Microsoft365 and local operations.

## Dependencies

`uv` for dependencies management

- msal and ... for authentication
- requests
- typer
- notmuch for advanced search in Maildir directories
- Microsoft Graph API
- Gmail API

## Setup

### Microsoft email

- App registration in Microsoft Entra ID
- API permissions: `User.Read`, `Mail.ReadWrite`, `offline_access`,
- Grant admin consent
- Create client secret

### GMail

Out of scope for this iteration.
