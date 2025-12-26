from __future__ import annotations
import os
import shutil
from pathlib import Path
from typing import Optional

def copy_to_secondary_output(source_file: str, file_type: str) -> Optional[str]:
    """
    Copy a file to a secondary output directory if mounted.

    For EPUBs, copies to /litkeeper/app/data/secondary-epubs if the directory exists
    (indicating a bind mount is configured).

    Args:
        source_file: Full path to the source file
        file_type: Type of file ('epub' or 'html')

    Returns:
        Path to the copied file if successful, None otherwise
    """
    if file_type != 'epub':
        return None

    secondary_path = Path(__file__).parent.parent / "data" / "secondary-epubs"

    if not secondary_path.exists():
        return None

    try:
        filename = os.path.basename(source_file)
        destination = secondary_path / filename

        shutil.copy2(source_file, str(destination))

        return str(destination)
    except (OSError, PermissionError, shutil.Error) as e:
        from .logger import log_error
        log_error(f"Failed to copy {file_type} to secondary output: {str(e)}", "secondary_output")
        return None
