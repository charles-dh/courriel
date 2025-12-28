"""Tests for sync CLI command.

Uses typer.testing.CliRunner for CLI tests.
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from courriel.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_config():
    """Mock configuration for tests."""
    return {
        "defaults": {
            "max_messages": 100,
            "days": 30,
            "sync_labels": ["INBOX", "SENT", "DRAFT"],
        },
        "accounts": {
            "personal": {
                "provider": "gmail",
                "client_id": "test-client-id.apps.googleusercontent.com",
                "mail_dir": "~/Mail/Personal",
            }
        },
    }


class TestSyncCommand:
    """Tests for sync command."""

    def test_requires_folder_or_all(self, runner: CliRunner):
        """sync command requires --folder or --all option."""
        result = runner.invoke(app, ["sync"])

        assert result.exit_code == 1
        assert "Must specify --folder or --all" in result.output

    def test_rejects_both_since_and_days(self, runner: CliRunner, mock_config):
        """sync command rejects both --since and --days."""
        with patch("courriel.cli.commands.sync.load_config", return_value=mock_config):
            result = runner.invoke(
                app,
                ["sync", "--folder", "INBOX", "--since", "2024-01-01", "--days", "30"],
            )

        assert result.exit_code == 1
        assert "Cannot specify both --since and --days" in result.output

    def test_requires_authentication(self, runner: CliRunner, mock_config):
        """sync command checks for authentication."""
        with (
            patch("courriel.cli.commands.sync.load_config", return_value=mock_config),
            patch(
                "courriel.cli.commands.sync.get_account",
                return_value=mock_config["accounts"]["personal"],
            ),
            patch("courriel.cli.commands.sync.get_credentials", return_value=None),
        ):
            result = runner.invoke(app, ["sync", "--folder", "INBOX"])

        assert result.exit_code == 1
        assert "Not authenticated" in result.output

    def test_rejects_unsupported_provider(self, runner: CliRunner):
        """sync command rejects non-Gmail providers."""
        config = {
            "accounts": {
                "work": {
                    "provider": "ms365",
                    "client_id": "test",
                    "mail_dir": "~/Mail",
                }
            }
        }
        with (
            patch("courriel.cli.commands.sync.load_config", return_value=config),
            patch(
                "courriel.cli.commands.sync.get_account",
                return_value=config["accounts"]["work"],
            ),
        ):
            result = runner.invoke(app, ["sync", "--folder", "INBOX"])

        assert result.exit_code == 1
        assert "not yet supported" in result.output

    def test_requires_account_config(self, runner: CliRunner):
        """sync command requires account configuration."""
        with (
            patch("courriel.cli.commands.sync.load_config", return_value={}),
            patch("courriel.cli.commands.sync.get_account", return_value=None),
        ):
            result = runner.invoke(app, ["sync", "--folder", "INBOX"])

        assert result.exit_code == 1
        assert "No account configured" in result.output

    def test_syncs_with_folder_option(self, runner: CliRunner, mock_config, tmp_path):
        """sync --folder syncs specified label."""
        mock_creds = MagicMock()
        mock_creds.valid = True

        mock_engine = MagicMock()
        mock_engine.sync.return_value = MagicMock(
            downloaded=5, skipped=0, errors=0, error_details=[]
        )

        with (
            patch("courriel.cli.commands.sync.load_config", return_value=mock_config),
            patch(
                "courriel.cli.commands.sync.get_account",
                return_value=mock_config["accounts"]["personal"],
            ),
            patch(
                "courriel.cli.commands.sync.get_credentials", return_value=mock_creds
            ),
            patch("courriel.cli.commands.sync.GmailClient"),
            patch("courriel.cli.commands.sync.MaildirStorage"),
            patch("courriel.cli.commands.sync.SyncState"),
            patch("courriel.cli.commands.sync.SyncEngine", return_value=mock_engine),
        ):
            result = runner.invoke(app, ["sync", "--folder", "INBOX"])

        assert result.exit_code == 0
        assert "5 messages downloaded" in result.output
        mock_engine.sync.assert_called_once()
        call_kwargs = mock_engine.sync.call_args.kwargs
        assert call_kwargs["labels"] == ["INBOX"]

    def test_syncs_all_default_labels(self, runner: CliRunner, mock_config):
        """sync --all syncs default labels from config."""
        mock_creds = MagicMock()
        mock_creds.valid = True

        mock_engine = MagicMock()
        mock_engine.sync.return_value = MagicMock(
            downloaded=10, skipped=5, errors=0, error_details=[]
        )

        with (
            patch("courriel.cli.commands.sync.load_config", return_value=mock_config),
            patch(
                "courriel.cli.commands.sync.get_account",
                return_value=mock_config["accounts"]["personal"],
            ),
            patch(
                "courriel.cli.commands.sync.get_credentials", return_value=mock_creds
            ),
            patch("courriel.cli.commands.sync.GmailClient"),
            patch("courriel.cli.commands.sync.MaildirStorage"),
            patch("courriel.cli.commands.sync.SyncState"),
            patch("courriel.cli.commands.sync.SyncEngine", return_value=mock_engine),
        ):
            result = runner.invoke(app, ["sync", "--all"])

        assert result.exit_code == 0
        assert "10 messages downloaded" in result.output
        assert "5 already synced" in result.output
        call_kwargs = mock_engine.sync.call_args.kwargs
        assert call_kwargs["labels"] == ["INBOX", "SENT", "DRAFT"]

    def test_passes_max_messages(self, runner: CliRunner, mock_config):
        """sync --max-messages passes limit to engine."""
        mock_creds = MagicMock()
        mock_creds.valid = True

        mock_engine = MagicMock()
        mock_engine.sync.return_value = MagicMock(
            downloaded=0, skipped=0, errors=0, error_details=[]
        )

        with (
            patch("courriel.cli.commands.sync.load_config", return_value=mock_config),
            patch(
                "courriel.cli.commands.sync.get_account",
                return_value=mock_config["accounts"]["personal"],
            ),
            patch(
                "courriel.cli.commands.sync.get_credentials", return_value=mock_creds
            ),
            patch("courriel.cli.commands.sync.GmailClient"),
            patch("courriel.cli.commands.sync.MaildirStorage"),
            patch("courriel.cli.commands.sync.SyncState"),
            patch("courriel.cli.commands.sync.SyncEngine", return_value=mock_engine),
        ):
            result = runner.invoke(
                app, ["sync", "--folder", "INBOX", "--max-messages", "50"]
            )

        assert result.exit_code == 0
        call_kwargs = mock_engine.sync.call_args.kwargs
        assert call_kwargs["max_messages"] == 50

    def test_passes_days_filter(self, runner: CliRunner, mock_config):
        """sync --days passes day filter to engine."""
        mock_creds = MagicMock()
        mock_creds.valid = True

        mock_engine = MagicMock()
        mock_engine.sync.return_value = MagicMock(
            downloaded=0, skipped=0, errors=0, error_details=[]
        )

        with (
            patch("courriel.cli.commands.sync.load_config", return_value=mock_config),
            patch(
                "courriel.cli.commands.sync.get_account",
                return_value=mock_config["accounts"]["personal"],
            ),
            patch(
                "courriel.cli.commands.sync.get_credentials", return_value=mock_creds
            ),
            patch("courriel.cli.commands.sync.GmailClient"),
            patch("courriel.cli.commands.sync.MaildirStorage"),
            patch("courriel.cli.commands.sync.SyncState"),
            patch("courriel.cli.commands.sync.SyncEngine", return_value=mock_engine),
        ):
            result = runner.invoke(app, ["sync", "--folder", "INBOX", "--days", "30"])

        assert result.exit_code == 0
        call_kwargs = mock_engine.sync.call_args.kwargs
        assert call_kwargs["days"] == 30

    def test_passes_since_filter(self, runner: CliRunner, mock_config):
        """sync --since passes date filter to engine."""
        from datetime import date

        mock_creds = MagicMock()
        mock_creds.valid = True

        mock_engine = MagicMock()
        mock_engine.sync.return_value = MagicMock(
            downloaded=0, skipped=0, errors=0, error_details=[]
        )

        with (
            patch("courriel.cli.commands.sync.load_config", return_value=mock_config),
            patch(
                "courriel.cli.commands.sync.get_account",
                return_value=mock_config["accounts"]["personal"],
            ),
            patch(
                "courriel.cli.commands.sync.get_credentials", return_value=mock_creds
            ),
            patch("courriel.cli.commands.sync.GmailClient"),
            patch("courriel.cli.commands.sync.MaildirStorage"),
            patch("courriel.cli.commands.sync.SyncState"),
            patch("courriel.cli.commands.sync.SyncEngine", return_value=mock_engine),
        ):
            result = runner.invoke(
                app, ["sync", "--folder", "INBOX", "--since", "2024-06-01"]
            )

        assert result.exit_code == 0
        call_kwargs = mock_engine.sync.call_args.kwargs
        assert call_kwargs["since"] == date(2024, 6, 1)

    def test_force_full_sync(self, runner: CliRunner, mock_config):
        """sync --full forces full sync."""
        mock_creds = MagicMock()
        mock_creds.valid = True

        mock_engine = MagicMock()
        mock_engine.sync.return_value = MagicMock(
            downloaded=0, skipped=0, errors=0, error_details=[]
        )

        with (
            patch("courriel.cli.commands.sync.load_config", return_value=mock_config),
            patch(
                "courriel.cli.commands.sync.get_account",
                return_value=mock_config["accounts"]["personal"],
            ),
            patch(
                "courriel.cli.commands.sync.get_credentials", return_value=mock_creds
            ),
            patch("courriel.cli.commands.sync.GmailClient"),
            patch("courriel.cli.commands.sync.MaildirStorage"),
            patch("courriel.cli.commands.sync.SyncState"),
            patch("courriel.cli.commands.sync.SyncEngine", return_value=mock_engine),
        ):
            result = runner.invoke(app, ["sync", "--folder", "INBOX", "--full"])

        assert result.exit_code == 0
        call_kwargs = mock_engine.sync.call_args.kwargs
        assert call_kwargs["force_full"] is True

    def test_exits_with_error_on_sync_errors(self, runner: CliRunner, mock_config):
        """sync exits with code 1 when sync has errors."""
        mock_creds = MagicMock()
        mock_creds.valid = True

        mock_engine = MagicMock()
        mock_engine.sync.return_value = MagicMock(
            downloaded=5,
            skipped=0,
            errors=2,
            error_details=["msg1: Error 1", "msg2: Error 2"],
        )

        with (
            patch("courriel.cli.commands.sync.load_config", return_value=mock_config),
            patch(
                "courriel.cli.commands.sync.get_account",
                return_value=mock_config["accounts"]["personal"],
            ),
            patch(
                "courriel.cli.commands.sync.get_credentials", return_value=mock_creds
            ),
            patch("courriel.cli.commands.sync.GmailClient"),
            patch("courriel.cli.commands.sync.MaildirStorage"),
            patch("courriel.cli.commands.sync.SyncState"),
            patch("courriel.cli.commands.sync.SyncEngine", return_value=mock_engine),
        ):
            result = runner.invoke(app, ["sync", "--folder", "INBOX"])

        assert result.exit_code == 1
        assert "2 errors" in result.output

    def test_handles_invalid_date_format(self, runner: CliRunner, mock_config):
        """sync rejects invalid date format."""
        mock_creds = MagicMock()
        mock_creds.valid = True

        with (
            patch("courriel.cli.commands.sync.load_config", return_value=mock_config),
            patch(
                "courriel.cli.commands.sync.get_account",
                return_value=mock_config["accounts"]["personal"],
            ),
            patch(
                "courriel.cli.commands.sync.get_credentials", return_value=mock_creds
            ),
        ):
            result = runner.invoke(
                app, ["sync", "--folder", "INBOX", "--since", "01-01-2024"]
            )

        assert result.exit_code != 0
        assert "Invalid date format" in result.output
