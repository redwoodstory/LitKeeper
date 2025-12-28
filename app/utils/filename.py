from __future__ import annotations
import re


def sanitize_filename(filename: str) -> str:
    """
    Remove unsafe characters from filename.

    Keeps only alphanumeric characters, dots, underscores, and hyphens.
    Strips leading/trailing dots and spaces to prevent issues with URLs and file systems.
    This prevents path traversal and ensures cross-platform compatibility.
    """
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '', filename)
    sanitized = sanitized.strip('.')
    return sanitized
