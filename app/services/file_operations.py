from __future__ import annotations
import os
import shutil
from pathlib import Path
from typing import Optional

def copy_to_external_path(source_file: str, file_type: str) -> Optional[str]:
    """
    Copy a file to an external path if EXTERNAL_EPUB_PATH is configured.

    For EPUBs, copies to the path specified in EXTERNAL_EPUB_PATH environment variable.
    This is useful for integrating with external apps like Calibre-Web.

    Args:
        source_file: Full path to the source file
        file_type: Type of file ('epub' or 'html')

    Returns:
        Path to the copied file if successful, None otherwise
    """
    if file_type != 'epub':
        return None

    external_path_str = os.getenv('EXTERNAL_EPUB_PATH')
    if not external_path_str:
        return None

    external_path = Path(external_path_str)
    
    if not external_path.exists():
        try:
            external_path.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            from .logger import log_error
            log_error(f"Failed to create external EPUB directory: {str(e)}", "external_output")
            return None

    try:
        filename = os.path.basename(source_file)
        destination = external_path / filename

        shutil.copy2(source_file, str(destination))

        return str(destination)
    except (OSError, PermissionError, shutil.Error) as e:
        from .logger import log_error
        log_error(f"Failed to copy {file_type} to external path: {str(e)}", "external_output")
        return None
