from __future__ import annotations
import os
from pathlib import Path

def is_running_in_docker() -> bool:
    """Check if the application is running inside a Docker container."""
    return os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv')

def check_mount_warning() -> dict[str, bool]:
    """
    Check if critical data directories have proper bind mounts.
    Uses marker files to detect if directories are persisted across container restarts.
    Returns dict with warning status, missing mounts, and whether library is enabled.
    """
    if not is_running_in_docker():
        return {"show_warning": False, "missing_mounts": [], "epubs_only": False}

    enable_library = os.getenv('ENABLE_LIBRARY', 'true').lower() == 'true'
    data_dir = Path(__file__).parent.parent / "data"

    required_dirs = {
        "epubs": data_dir / "epubs",
    }

    library_dirs = {
        "html": data_dir / "html",
        "covers": data_dir / "covers"
    }

    if enable_library:
        dirs_to_check = {**required_dirs, **library_dirs}
    else:
        dirs_to_check = required_dirs

    missing_mounts = []

    for name, dir_path in dirs_to_check.items():
        marker_file = dir_path / ".mount_marker"

        if not dir_path.exists():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
            except (OSError, PermissionError):
                missing_mounts.append(name)
                continue

        if not marker_file.exists():
            try:
                marker_file.write_text("This file indicates a bind mount is configured.")
                missing_mounts.append(name)
            except (OSError, PermissionError):
                missing_mounts.append(name)

    epubs_only = missing_mounts == ["epubs"]

    return {
        "show_warning": len(missing_mounts) > 0,
        "missing_mounts": missing_mounts,
        "epubs_only": epubs_only
    }

def check_secret_key_warning() -> bool:
    """
    Check if SECRET_KEY is properly configured.
    Returns True if warning should be shown.
    """
    secret_key = os.getenv('SECRET_KEY')

    if not secret_key:
        return True

    if secret_key == 'your-secret-key-here':
        return True

    if len(secret_key) < 32:
        return True

    return False
