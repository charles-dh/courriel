"""Search module for local and remote email search.

v1: Local search via notmuch CLI wrapper.
v2: Remote search via Gmail/MS365 APIs (planned).
"""

from .local import (
    NotmuchDatabaseError,
    NotmuchError,
    NotmuchNotFoundError,
    search_local,
)
from .models import SearchResult

__all__ = [
    "SearchResult",
    "search_local",
    "NotmuchError",
    "NotmuchNotFoundError",
    "NotmuchDatabaseError",
]
