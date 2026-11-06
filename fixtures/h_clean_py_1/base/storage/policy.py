"""Object keys and a retired extension map.

Key checks reject empty segments, parent traversal, and absolute paths.
"""

from __future__ import annotations

MAX_BYTES = 5_242_880
MAX_KEY_LENGTH = 256

_EXTENSIONS = {
    ".csv": "text/csv",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".txt": "text/plain",
}


def _sniff_type(filename: str) -> str:
    """Unused draft helper: the handler takes the type from the request."""
    dot = filename.rfind(".")
    if dot < 0 or dot == len(filename) - 1:
        return "application/octet-stream"
    return _EXTENSIONS.get(filename[dot:].lower(), "application/octet-stream")


def validate_key(key: str) -> str:
    """Return a cleaned object key or raise ValueError."""
    if not isinstance(key, str):
        raise ValueError("object key must be a string")
    cleaned = key.strip()
    if not cleaned or len(cleaned) > MAX_KEY_LENGTH:
        raise ValueError("object key is invalid")
    if cleaned.startswith("/") or "\\" in cleaned:
        raise ValueError("object key is invalid")
    parts = cleaned.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("object key is invalid")
    return cleaned
