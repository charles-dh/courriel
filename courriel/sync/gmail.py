"""Gmail API client for email synchronization.

Wraps the Gmail API to provide a clean interface for sync operations.
Handles authentication, pagination, and data transformation.
"""

import base64

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError  # noqa: F401 - re-exported for callers

from courriel.auth.gmail import _load_token, _save_token


def get_credentials() -> Credentials | None:
    """Get Gmail credentials for API access.

    Returns the cached credentials object which can be used with
    googleapiclient. Automatically refreshes expired tokens if a
    refresh token is available. Returns None if not authenticated
    or if refresh fails.

    Returns:
        Credentials object or None if not authenticated.
    """
    creds = _load_token()
    if not creds:
        return None

    # If token is expired but we have a refresh token, try to refresh
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)  # Persist refreshed token
        except Exception:
            # Refresh failed - token is no longer valid
            return None

    # Return credentials only if valid
    return creds if creds.valid else None


class GmailClient:
    """Client for Gmail API operations.

    Provides methods for listing labels, messages, and fetching email content.
    Handles pagination automatically for list operations.

    Example:
        creds = get_credentials()
        client = GmailClient(creds)
        labels = client.list_labels()
        messages = client.list_messages("INBOX", max_results=50)
    """

    def __init__(self, credentials: Credentials):
        """Initialize Gmail client with credentials.

        Args:
            credentials: Google OAuth credentials object.
        """
        self._credentials = credentials
        # Build the Gmail API service
        # The service is the main entry point for all Gmail API calls
        self._service = build("gmail", "v1", credentials=credentials)

    def list_labels(self) -> list[dict]:
        """List all labels in the user's mailbox.

        Returns:
            List of label dicts with keys: id, name, type.
            System labels have type='system', user labels have type='user'.
        """
        result = self._service.users().labels().list(userId="me").execute()
        labels = result.get("labels", [])

        # Return simplified label info
        return [
            {
                "id": label["id"],
                "name": label["name"],
                "type": label.get("type", "user"),
            }
            for label in labels
        ]

    def list_messages(
        self,
        label_id: str | None = None,
        query: str | None = None,
        max_results: int = 100,
    ) -> list[str]:
        """List message IDs matching the given criteria.

        Handles pagination automatically to fetch up to max_results messages.

        Args:
            label_id: Filter by label ID (e.g., "INBOX", "SENT").
            query: Gmail search query (e.g., "after:2024/01/01").
            max_results: Maximum number of message IDs to return.

        Returns:
            List of message ID strings.
        """
        message_ids = []
        page_token = None

        while len(message_ids) < max_results:
            # Calculate how many more we need (API max per page is 500)
            remaining = max_results - len(message_ids)
            page_size = min(remaining, 500)

            # Build request parameters
            params = {
                "userId": "me",
                "maxResults": page_size,
            }
            if label_id:
                params["labelIds"] = [label_id]
            if query:
                params["q"] = query
            if page_token:
                params["pageToken"] = page_token

            result = self._service.users().messages().list(**params).execute()

            # Extract message IDs from response
            messages = result.get("messages", [])
            for msg in messages:
                message_ids.append(msg["id"])
                if len(message_ids) >= max_results:
                    break

            # Check for more pages
            page_token = result.get("nextPageToken")
            if not page_token:
                break

        return message_ids

    def get_message(self, message_id: str) -> dict:
        """Get a single message with full content.

        Fetches the message in RAW format (base64url-encoded RFC 2822)
        and decodes it to bytes for Maildir storage.

        Args:
            message_id: The message ID to fetch.

        Returns:
            Dict with keys:
            - id: Message ID
            - threadId: Thread ID
            - labelIds: List of label IDs applied to this message
            - historyId: History ID for incremental sync
            - raw: Decoded message bytes (RFC 2822 format)
        """
        result = (
            self._service.users()
            .messages()
            .get(userId="me", id=message_id, format="raw")
            .execute()
        )

        # Decode the raw message from base64url to bytes
        # Gmail uses URL-safe base64 encoding
        raw_base64 = result.get("raw", "")
        raw_bytes = base64.urlsafe_b64decode(raw_base64)

        return {
            "id": result["id"],
            "threadId": result["threadId"],
            "labelIds": result.get("labelIds", []),
            "historyId": result["historyId"],
            "raw": raw_bytes,
        }

    def list_history(
        self,
        start_history_id: str,
        label_id: str | None = None,
    ) -> dict:
        """List changes since a given history ID.

        Used for incremental sync - only fetches changes since last sync.
        The History API tracks message additions, deletions, and label changes.

        Args:
            start_history_id: History ID from previous sync.
            label_id: Optional label ID to filter history.

        Returns:
            Dict with keys:
            - history: List of change records (may be empty if no changes)
            - historyId: Current history ID (store for next sync)

        Raises:
            HttpError: If history ID is expired (404) or other API error.
        """
        history_records = []
        page_token = None
        current_history_id = start_history_id

        while True:
            # Build request parameters
            params = {
                "userId": "me",
                "startHistoryId": start_history_id,
                "maxResults": 500,
            }
            if label_id:
                params["labelId"] = label_id
            if page_token:
                params["pageToken"] = page_token

            # This may raise HttpError 404 if historyId is too old (~1 week)
            result = self._service.users().history().list(**params).execute()

            # Collect history records
            records = result.get("history", [])
            history_records.extend(records)

            # Track the latest history ID
            current_history_id = result.get("historyId", current_history_id)

            # Check for more pages
            page_token = result.get("nextPageToken")
            if not page_token:
                break

        return {
            "history": history_records,
            "historyId": current_history_id,
        }
