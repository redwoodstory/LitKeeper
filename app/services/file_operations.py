from __future__ import annotations
import os
import shutil
from pathlib import Path
from typing import Optional

def copy_to_secondary_output(source_file: str, file_type: str) -> Optional[str]:
    """
    Copy a file to a secondary output directory if configured.

    Args:
        source_file: Full path to the source file
        file_type: Type of file ('epub' or 'html')

    Returns:
        Path to the copied file if successful, None otherwise
    """
    if file_type == 'epub':
        secondary_path = os.getenv('SECONDARY_EPUB_OUTPUT_PATH')
    else:
        return None

    if not secondary_path:
        return None

    secondary_path = secondary_path.strip()
    if not secondary_path:
        return None

    try:
        Path(secondary_path).mkdir(parents=True, exist_ok=True)

        filename = os.path.basename(source_file)
        destination = os.path.join(secondary_path, filename)

        shutil.copy2(source_file, destination)

        return destination
    except (OSError, PermissionError, shutil.Error) as e:
        from .logger import log_error
        log_error(f"Failed to copy {file_type} to secondary output: {str(e)}", "secondary_output")
        return None
