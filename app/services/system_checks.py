from __future__ import annotations
import os
from pathlib import Path
from typing import Any


def is_running_in_docker() -> bool:
    """Check if the application is running inside a Docker container."""
    return os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv')


def check_legacy_mounts() -> dict[str, Any]:
    """
    Check if legacy V1 bind mounts are present.
    V1 used: ./epubs:/litkeeper/app/data/epubs and ./logs:/litkeeper/app/data/logs
    If detected, user is likely upgrading from V1 and should see migration info.
    Returns dict with legacy mount detection status.
    """
    if not is_running_in_docker():
        return {"has_legacy_mounts": False, "legacy_mount_names": []}

    app_dir = Path(__file__).parent.parent
    legacy_epubs = app_dir / "data" / "epubs"
    legacy_logs = app_dir / "data" / "logs"

    legacy_mounts = []
    
    if os.path.ismount(str(legacy_epubs)):
        legacy_mounts.append("data/epubs")
    
    if os.path.ismount(str(legacy_logs)):
        legacy_mounts.append("data/logs")

    return {
        "has_legacy_mounts": len(legacy_mounts) > 0,
        "legacy_mount_names": legacy_mounts
    }


def check_mount_warning() -> dict[str, Any]:
    """
    Check if the data and stories directories are real bind mounts.
    Uses os.path.ismount() to ask the OS directly — no marker files needed,
    no false positives, works reliably inside Linux containers.
    Returns dict with warning status and list of missing mounts.
    """
    if not is_running_in_docker():
        return {"show_warning": False, "missing_mounts": [], "epubs_only": False}

    app_dir = Path(__file__).parent.parent
    data_dir = app_dir / "data"
    stories_dir = app_dir / "stories"

    missing_mounts = []
    
    if not os.path.ismount(str(data_dir)):
        missing_mounts.append("data")
    
    if not os.path.ismount(str(stories_dir)):
        missing_mounts.append("stories")

    return {
        "show_warning": len(missing_mounts) > 0,
        "missing_mounts": missing_mounts,
        "epubs_only": False
    }
