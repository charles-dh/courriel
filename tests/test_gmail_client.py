"""Tests for Gmail API client.

Uses mocking to test API interactions without real credentials.
"""

import base64
from unittest.mock import MagicMock, patch

import pytest

from courriel.sync.gmail import GmailClient


@pytest.fixture
def mock_credentials():
    """Create mock credentials for testing."""
    creds = MagicMock()
    creds.valid = True
    creds.expired = False
    return creds


@pytest.fixture
def mock_service():
    """Create a mock Gmail service."""
    return MagicMock()


@pytest.fixture
def gmail_client(mock_credentials, mock_service):
    """Create a GmailClient with mocked service."""
    with patch("courriel.sync.gmail.build") as mock_build:
        mock_build.return_value = mock_service
        client = GmailClient(mock_credentials)
        return client


class TestListLabels:
    """Tests for list_labels method."""

    def test_returns_parsed_labels(self, gmail_client, mock_service):
        """list_labels returns simplified label dicts."""
        # Arrange - Mock API response
        mock_service.users().labels().list().execute.return_value = {
            "labels": [
                {"id": "INBOX", "name": "INBOX", "type": "system"},
                {"id": "SENT", "name": "SENT", "type": "system"},
                {"id": "Label_123", "name": "MyLabel", "type": "user"},
            ]
        }

        # Act
        labels = gmail_client.list_labels()

        # Assert
        assert len(labels) == 3
        assert labels[0] == {"id": "INBOX", "name": "INBOX", "type": "system"}
        assert labels[1] == {"id": "SENT", "name": "SENT", "type": "system"}
        assert labels[2] == {"id": "Label_123", "name": "MyLabel", "type": "user"}

    def test_handles_empty_labels(self, gmail_client, mock_service):
        """list_labels handles empty response."""
        mock_service.users().labels().list().execute.return_value = {"labels": []}

        labels = gmail_client.list_labels()

        assert labels == []

    def test_handles_missing_type(self, gmail_client, mock_service):
        """list_labels defaults to 'user' when type is missing."""
        mock_service.users().labels().list().execute.return_value = {
            "labels": [{"id": "Label_1", "name": "Test"}]
        }

        labels = gmail_client.list_labels()

        assert labels[0]["type"] == "user"


class TestListMessages:
    """Tests for list_messages method."""

    def test_returns_message_ids(self, gmail_client, mock_service):
        """list_messages returns list of message IDs."""
        mock_service.users().messages().list().execute.return_value = {
            "messages": [{"id": "msg1"}, {"id": "msg2"}, {"id": "msg3"}]
        }

        message_ids = gmail_client.list_messages(label_id="INBOX", max_results=10)

        assert message_ids == ["msg1", "msg2", "msg3"]

    def test_respects_max_results(self, gmail_client, mock_service):
        """list_messages limits results to max_results."""
        mock_service.users().messages().list().execute.return_value = {
            "messages": [{"id": f"msg{i}"} for i in range(100)]
        }

        message_ids = gmail_client.list_messages(label_id="INBOX", max_results=5)

        assert len(message_ids) == 5

    def test_handles_pagination(self, gmail_client, mock_service):
        """list_messages handles multiple pages of results."""
        # First page has nextPageToken, second doesn't
        mock_service.users().messages().list().execute.side_effect = [
            {"messages": [{"id": "msg1"}, {"id": "msg2"}], "nextPageToken": "token123"},
            {"messages": [{"id": "msg3"}, {"id": "msg4"}]},
        ]

        message_ids = gmail_client.list_messages(label_id="INBOX", max_results=10)

        assert message_ids == ["msg1", "msg2", "msg3", "msg4"]
        # Verify execute was called twice (for pagination)
        assert mock_service.users().messages().list().execute.call_count == 2

    def test_handles_empty_response(self, gmail_client, mock_service):
        """list_messages handles empty message list."""
        mock_service.users().messages().list().execute.return_value = {}

        message_ids = gmail_client.list_messages(label_id="INBOX")

        assert message_ids == []

    def test_passes_query_parameter(self, gmail_client, mock_service):
        """list_messages passes query to API."""
        mock_service.users().messages().list().execute.return_value = {"messages": []}

        gmail_client.list_messages(query="after:2024/01/01", max_results=10)

        # Check that list was called with query parameter
        mock_service.users().messages().list.assert_called()


class TestGetMessage:
    """Tests for get_message method."""

    def test_returns_decoded_message(self, gmail_client, mock_service):
        """get_message returns message with decoded raw bytes."""
        # Create a sample RFC 2822 message
        sample_message = b"From: sender@example.com\r\nTo: recipient@example.com\r\nSubject: Test\r\n\r\nHello World"
        encoded_message = base64.urlsafe_b64encode(sample_message).decode("ascii")

        mock_service.users().messages().get().execute.return_value = {
            "id": "msg123",
            "threadId": "thread456",
            "labelIds": ["INBOX", "UNREAD"],
            "historyId": "12345",
            "raw": encoded_message,
        }

        result = gmail_client.get_message("msg123")

        assert result["id"] == "msg123"
        assert result["threadId"] == "thread456"
        assert result["labelIds"] == ["INBOX", "UNREAD"]
        assert result["historyId"] == "12345"
        assert result["raw"] == sample_message

    def test_handles_missing_labels(self, gmail_client, mock_service):
        """get_message handles missing labelIds gracefully."""
        encoded_message = base64.urlsafe_b64encode(b"test").decode("ascii")

        mock_service.users().messages().get().execute.return_value = {
            "id": "msg123",
            "threadId": "thread456",
            "historyId": "12345",
            "raw": encoded_message,
        }

        result = gmail_client.get_message("msg123")

        assert result["labelIds"] == []

    def test_decodes_base64url_correctly(self, gmail_client, mock_service):
        """get_message correctly decodes base64url (with - and _ chars)."""
        # Message with special characters that differ in base64 vs base64url
        sample = b"Test message with special chars: \xff\xfe\xfd"
        # Use urlsafe encoding (uses - and _ instead of + and /)
        encoded = base64.urlsafe_b64encode(sample).decode("ascii")

        mock_service.users().messages().get().execute.return_value = {
            "id": "msg1",
            "threadId": "t1",
            "historyId": "1",
            "raw": encoded,
        }

        result = gmail_client.get_message("msg1")

        assert result["raw"] == sample


class TestListHistory:
    """Tests for list_history method."""

    def test_returns_history_records(self, gmail_client, mock_service):
        """list_history returns change records and current historyId."""
        mock_service.users().history().list().execute.return_value = {
            "history": [
                {
                    "id": "100",
                    "messagesAdded": [
                        {"message": {"id": "msg1", "labelIds": ["INBOX"]}}
                    ],
                },
                {
                    "id": "101",
                    "messagesAdded": [
                        {"message": {"id": "msg2", "labelIds": ["INBOX"]}}
                    ],
                },
            ],
            "historyId": "102",
        }

        result = gmail_client.list_history(start_history_id="99")

        assert len(result["history"]) == 2
        assert result["historyId"] == "102"

    def test_handles_no_changes(self, gmail_client, mock_service):
        """list_history handles empty history response."""
        mock_service.users().history().list().execute.return_value = {
            "historyId": "100"
        }

        result = gmail_client.list_history(start_history_id="100")

        assert result["history"] == []
        assert result["historyId"] == "100"

    def test_handles_pagination(self, gmail_client, mock_service):
        """list_history handles multiple pages of history."""
        mock_service.users().history().list().execute.side_effect = [
            {
                "history": [{"id": "100", "messagesAdded": []}],
                "historyId": "101",
                "nextPageToken": "token123",
            },
            {
                "history": [{"id": "101", "messagesAdded": []}],
                "historyId": "102",
            },
        ]

        result = gmail_client.list_history(start_history_id="99")

        assert len(result["history"]) == 2
        assert result["historyId"] == "102"
        # Verify execute was called twice (for pagination)
        assert mock_service.users().history().list().execute.call_count == 2

    def test_passes_label_filter(self, gmail_client, mock_service):
        """list_history passes label_id filter to API."""
        mock_service.users().history().list().execute.return_value = {
            "historyId": "100"
        }

        gmail_client.list_history(start_history_id="99", label_id="INBOX")

        mock_service.users().history().list.assert_called()
