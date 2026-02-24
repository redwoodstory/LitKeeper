from __future__ import annotations
import os
from pathlib import Path
from typing import Any


def is_running_in_docker() -> bool:
    """Check if the application is running inside a Docker container."""
    return os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv')


def check_mount_warning() -> dict[str, Any]:
    """
    Check if the stories directory is a real bind mount.
    Uses os.path.ismount() to ask the OS directly — no marker files needed,
    no false positives, works reliably inside Linux containers.
    Returns dict with warning status.
    """
    if not is_running_in_docker():
        return {"show_warning": False, "missing_mounts": [], "epubs_only": False}

    stories_dir = Path(__file__).parent.parent / "stories"

    # os.path.ismount() returns True when the path is a mount point (bind mount, volume, etc.)
    if os.path.ismount(str(stories_dir)):
        return {"show_warning": False, "missing_mounts": [], "epubs_only": False}

    return {"show_warning": True, "missing_mounts": ["stories"], "epubs_only": False}
