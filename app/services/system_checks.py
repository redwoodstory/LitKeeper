from __future__ import annotations
import os
from pathlib import Path

def is_running_in_docker() -> bool:
    """Check if the application is running inside a Docker container."""
    return os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv')

def check_mount_warning() -> dict[str, bool]:
    """
    Check if stories directory has proper bind mount.
    The startup script creates a marker file - if it's missing, the mount wasn't configured.
    Returns dict with warning status.
    """
    if not is_running_in_docker():
        return {"show_warning": False, "missing_mounts": [], "epubs_only": False}

    app_dir = Path(__file__).parent.parent
    stories_dir = app_dir / "stories"
    marker_file = stories_dir / ".mount_marker"

    # If marker file exists, mount is properly configured
    if marker_file.exists():
        return {"show_warning": False, "missing_mounts": [], "epubs_only": False}

    # No marker file means no bind mount was detected
    return {"show_warning": True, "missing_mounts": ["stories"], "epubs_only": False}
