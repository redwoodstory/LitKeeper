from __future__ import annotations
import re


def sanitize_filename(filename: str) -> str:
    """
    Remove unsafe characters from filename.

    Keeps only alphanumeric characters, dots, underscores, and hyphens.
    This prevents path traversal and ensures cross-platform compatibility.
    """
    return re.sub(r'[^a-zA-Z0-9._-]', '', filename)
