from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .models import ConditionSnapshot


@dataclass
class CacheEntry:
    last_modified: Optional[str] = None
    snapshot: Optional[ConditionSnapshot] = None


class LastModifiedCache:
    """In-memory cache that tracks Last-Modified headers and parsed snapshots."""

    def __init__(self) -> None:
        self._entries: Dict[str, CacheEntry] = {}

    def get_conditional_headers(self, url: str) -> Dict[str, str]:
        entry = self._entries.get(url)
        if entry and entry.last_modified:
            return {"If-Modified-Since": entry.last_modified}
        return {}

    def update(self, url: str, last_modified: Optional[str], snapshot: ConditionSnapshot) -> None:
        self._entries[url] = CacheEntry(last_modified=last_modified, snapshot=snapshot)

    def get_snapshot(self, url: str) -> Optional[ConditionSnapshot]:
        entry = self._entries.get(url)
        if entry:
            return entry.snapshot
        return None
