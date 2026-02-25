"""Tests for the read command and message parsing.

Tests both the parsing module (courriel.read.read_message) and the CLI
command (courriel read <path>).
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from courriel.cli.main import app
from courriel.read import read_message

# --- Sample email fixtures ---

PLAIN_EMAIL = b"""\
From: Alice Smith <alice@example.com>
To: Bob Jones <bob@example.com>
Cc: Charlie <charlie@example.com>
Date: Mon, 15 Jan 2024 10:00:00 +0000
Subject: Test message
Message-ID: <abc123@example.com>
In-Reply-To: <prev456@example.com>
Content-Type: text/plain; charset="utf-8"

Hello Bob,

This is a test message.

Best,
Alice
"""

MULTIPART_EMAIL = b"""\
From: Alice Smith <alice@example.com>
To: Bob Jones <bob@example.com>
Date: Tue, 16 Jan 2024 12:00:00 +0000
Subject: Multipart with attachment
Message-ID: <multi789@example.com>
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: text/plain; charset="utf-8"

Plain text body.
--boundary123
Content-Type: text/html; charset="utf-8"

<html><body><p>HTML body.</p></body></html>
--boundary123
Content-Type: application/pdf; name="report.pdf"
Content-Disposition: attachment; filename="report.pdf"
Content-Transfer-Encoding: base64

SlZCRVJpMHhMamNLJWVvZgo=
--boundary123--
"""

HTML_ONLY_EMAIL = b"""\
From: Newsletter <news@example.com>
To: bob@example.com
Date: Wed, 17 Jan 2024 08:00:00 +0000
Subject: HTML only
Message-ID: <html999@example.com>
Content-Type: text/html; charset="utf-8"

<html><body><h1>Title</h1><p>Some content here.</p></body></html>
"""


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def plain_email_file(tmp_path: Path) -> Path:
    """Write a plain text email to a temp file."""
    p = tmp_path / "plain_msg"
    p.write_bytes(PLAIN_EMAIL)
    return p


@pytest.fixture
def multipart_email_file(tmp_path: Path) -> Path:
    """Write a multipart email to a temp file."""
    p = tmp_path / "multi_msg"
    p.write_bytes(MULTIPART_EMAIL)
    return p


@pytest.fixture
def html_only_email_file(tmp_path: Path) -> Path:
    """Write an HTML-only email to a temp file."""
    p = tmp_path / "html_msg"
    p.write_bytes(HTML_ONLY_EMAIL)
    return p


# --- Parsing tests ---


class TestReadMessage:
    """Tests for read_message() parsing function."""

    def test_plain_email_headers(self, plain_email_file: Path):
        msg = read_message(plain_email_file)
        assert msg.from_addr == "Alice Smith <alice@example.com>"
        assert msg.to_addrs == ["Bob Jones <bob@example.com>"]
        assert msg.cc_addrs == ["Charlie <charlie@example.com>"]
        assert msg.bcc_addrs == []
        assert msg.subject == "Test message"
        assert msg.message_id == "<abc123@example.com>"
        assert msg.in_reply_to == "<prev456@example.com>"

    def test_plain_email_body(self, plain_email_file: Path):
        msg = read_message(plain_email_file)
        assert msg.body_plain is not None
        assert "Hello Bob" in msg.body_plain
        assert "test message" in msg.body_plain
        assert msg.body_html is None

    def test_plain_email_no_attachments(self, plain_email_file: Path):
        msg = read_message(plain_email_file)
        assert msg.attachments == []

    def test_multipart_bodies(self, multipart_email_file: Path):
        msg = read_message(multipart_email_file)
        assert msg.body_plain is not None
        assert "Plain text body" in msg.body_plain
        assert msg.body_html is not None
        assert "HTML body" in msg.body_html

    def test_multipart_attachment(self, multipart_email_file: Path):
        msg = read_message(multipart_email_file)
        assert len(msg.attachments) == 1
        att = msg.attachments[0]
        assert att["filename"] == "report.pdf"
        assert att["content_type"] == "application/pdf"
        assert att["size"] > 0

    def test_html_only_email(self, html_only_email_file: Path):
        msg = read_message(html_only_email_file)
        assert msg.body_plain is None
        assert msg.body_html is not None
        assert "Title" in msg.body_html

    def test_date_parsing(self, plain_email_file: Path):
        msg = read_message(plain_email_file)
        assert msg.date.year == 2024
        assert msg.date.month == 1
        assert msg.date.day == 15

    def test_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            read_message(tmp_path / "nonexistent")

    def test_to_dict(self, plain_email_file: Path):
        msg = read_message(plain_email_file)
        d = msg.to_dict()
        assert d["from"] == "Alice Smith <alice@example.com>"
        assert d["subject"] == "Test message"
        assert d["message_id"] == "<abc123@example.com>"
        assert isinstance(d["date"], str)  # ISO format string


# --- CLI tests ---


class TestReadCLI:
    """Tests for the read CLI command."""

    def test_text_output(self, runner: CliRunner, plain_email_file: Path):
        result = runner.invoke(app, ["read", str(plain_email_file)])
        assert result.exit_code == 0
        assert "From: Alice Smith <alice@example.com>" in result.output
        assert "Subject: Test message" in result.output
        assert "Hello Bob" in result.output

    def test_json_output(self, runner: CliRunner, plain_email_file: Path):
        result = runner.invoke(app, ["read", "--output", "json", str(plain_email_file)])
        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        assert data["from"] == "Alice Smith <alice@example.com>"
        assert data["subject"] == "Test message"

    def test_headers_output(self, runner: CliRunner, plain_email_file: Path):
        result = runner.invoke(
            app, ["read", "--output", "headers", str(plain_email_file)]
        )
        assert result.exit_code == 0
        assert "From: Alice Smith" in result.output
        assert "Subject: Test message" in result.output
        # Body should NOT appear in headers-only output
        assert "Hello Bob" not in result.output

    def test_raw_output(self, runner: CliRunner, plain_email_file: Path):
        result = runner.invoke(app, ["read", "--output", "raw", str(plain_email_file)])
        assert result.exit_code == 0
        # Raw output should contain the original email headers
        assert "Message-ID: <abc123@example.com>" in result.output
        assert "Hello Bob" in result.output

    def test_file_not_found(self, runner: CliRunner):
        result = runner.invoke(app, ["read", "/nonexistent/path/to/email"])
        assert result.exit_code == 1
        assert "File not found" in result.output

    def test_invalid_output_format(self, runner: CliRunner, plain_email_file: Path):
        result = runner.invoke(app, ["read", "--output", "csv", str(plain_email_file)])
        assert result.exit_code == 1
        assert "Invalid output format" in result.output

    def test_html_fallback_in_text_mode(
        self, runner: CliRunner, html_only_email_file: Path
    ):
        """When no plain text body, text output should show stripped HTML."""
        result = runner.invoke(app, ["read", str(html_only_email_file)])
        assert result.exit_code == 0
        assert "Title" in result.output
        assert "Some content here" in result.output
        # HTML tags should be stripped
        assert "<html>" not in result.output

    def test_attachment_info(self, runner: CliRunner, multipart_email_file: Path):
        result = runner.invoke(app, ["read", str(multipart_email_file)])
        assert result.exit_code == 0
        assert "report.pdf" in result.output
        assert "application/pdf" in result.output
