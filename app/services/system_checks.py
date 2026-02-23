from __future__ import annotations
import os
from pathlib import Path

def is_running_in_docker() -> bool:
    """Check if the application is running inside a Docker container."""
    return os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv')

from typing import Any

def check_mount_warning() -> dict[str, Any]:
    """
    Check if stories directory has proper bind mount.
    The startup script creates a marker file - if it's missing, the mount wasn't configured.
    Returns dict with warning status.
    """
    if not is_running_in_docker():
        return {"show_warning": False, "missing_mounts": [], "epubs_only": False}

    app_dir = Path(__file__).parent.parent
    stories_dir = app_dir / "stories"
    marker_file = stories_dir / ".container_default"

    # If the build-time marker file exists, it means we are still seeing the 
    # container's ephemeral filesystem instead of the user's mapped volume.
    if marker_file.exists():
        return {"show_warning": True, "missing_mounts": ["stories"], "epubs_only": False}

    # The marker file is hidden by the bind mount
    return {"show_warning": False, "missing_mounts": [], "epubs_only": False}
