"""In-memory object store.

The instance owns the mapping. One thread may use a store.
"""

from __future__ import annotations


class MemoryObjectStore:
    """Stores object bodies keyed by the validated object key."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def put(self, key: str, body: bytes) -> None:
        self._objects[key] = bytes(body)

    def get(self, key: str) -> bytes:
        try:
            return self._objects[key]
        except KeyError as exc:
            raise KeyError(key) from exc

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key in self._objects
