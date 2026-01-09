import os
from pathlib import Path
from typing import Optional
from urllib.parse import unquote


def is_safe_path(base_dir: str, filepath: str) -> bool:
    """
    Validates that filepath doesn't escape base_dir via path traversal.

    Args:
        base_dir: The directory that should contain the file
        filepath: The requested file path (can be relative or absolute)

    Returns:
        True if the path is safe, False otherwise
    """
    if not filepath:
        return False

    if '\0' in filepath:
        return False

    if filepath.startswith('/') or filepath.startswith('\\'):
        return False

    if '..' in filepath:
        return False

    try:
        base_path = Path(base_dir).resolve()
        requested_path = (Path(base_dir) / filepath).resolve()

        return requested_path.is_relative_to(base_path)
    except (ValueError, RuntimeError):
        return False


def sanitize_zip_path(zip_path: str) -> Optional[str]:
    """
    Sanitize paths from ZIP archives (EPUB files).

    Args:
        zip_path: Path from inside a ZIP file

    Returns:
        The sanitized path if safe, None otherwise
    """
    if not zip_path:
        return None

    if '\0' in zip_path:
        return None

    decoded_path = unquote(zip_path)
    if '\0' in decoded_path:
        return None

    if decoded_path.startswith('/') or decoded_path.startswith('\\'):
        return None

    if '..' in decoded_path:
        return None

    path_obj = Path(decoded_path)
    if path_obj.is_absolute():
        return None

    parts = path_obj.parts
    if any(part in ('..', '.', '') or part.startswith('.') for part in parts):
        return None

    return decoded_path


def validate_file_in_directory(base_dir: str, filename: str) -> bool:
    """
    Validates that a filename resolves to a path within base_dir.

    Args:
        base_dir: The directory that should contain the file
        filename: The filename or relative path

    Returns:
        True if the resolved path is within base_dir, False otherwise
    """
    try:
        base_path = Path(base_dir).resolve()
        file_path = Path(os.path.join(base_dir, filename)).resolve()

        return file_path.is_relative_to(base_path)
    except (ValueError, RuntimeError):
        return False
