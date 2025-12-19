"""Default configuration template.

This template is written to ~/.config/courriel/config.toml
when running `courriel config init`.
"""

CONFIG_TEMPLATE = """\
# Courriel Configuration
# Documentation: https://github.com/user/courriel

[defaults]
max_messages = 100
days = 30

# Add your email accounts below.
# Example Microsoft 365 account:
#
# [accounts.work]
# provider = "ms365"
# tenant_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
# client_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
# mail_dir = "~/Mail/Work"
#
# Get tenant_id and client_id from your Azure app registration.
# For client_secret, use the COURRIEL_MS365_CLIENT_SECRET environment variable.
#
# Example Gmail account:
#
# [accounts.personal]
# provider = "gmail"
# client_id = "xxxxxx.apps.googleusercontent.com"
# mail_dir = "~/Mail/Personal"
#
# Get client_id and client_secret from Google Cloud Console OAuth credentials.
# For client_secret, use the COURRIEL_GMAIL_CLIENT_SECRET environment variable.
#
# After adding an account, authenticate with:
#   courriel config auth --account work
"""
