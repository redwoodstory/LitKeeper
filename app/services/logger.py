from __future__ import annotations
import logging
import sys
from typing import Optional

def _setup_console_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Configure a logger with console/stdout handler for Docker logs."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger

action_logger = _setup_console_logger('litkeeper.action')
error_logger = _setup_console_logger('litkeeper.error', logging.ERROR)
url_logger = _setup_console_logger('litkeeper.url')

def _log_startup_info() -> None:
    """Log startup notification configuration information."""
    if action_logger:
        from .notifier import NOTIFICATION_URLS_RAW, NOTIFICATION_URLS, ENABLE_NOTIFICATIONS
        action_logger.info("[STARTUP] Notification configuration loaded")
        action_logger.info(f"[STARTUP] NOTIFICATION_URLS_RAW: '{NOTIFICATION_URLS_RAW[:100]}...'")
        action_logger.info(f"[STARTUP] NOTIFICATION_URLS_RAW length: {len(NOTIFICATION_URLS_RAW)}")
        action_logger.info(f"[STARTUP] NOTIFICATION_URLS after split: {len(NOTIFICATION_URLS)} URLs")
        for i, url in enumerate(NOTIFICATION_URLS):
            url_preview = url[:50] + "..." if len(url) > 50 else url
            action_logger.info(f"[STARTUP] URL {i+1}: '{url_preview}' (length: {len(url)})")
        action_logger.info(f"[STARTUP] ENABLE_NOTIFICATIONS: {ENABLE_NOTIFICATIONS}")

def log_action(message: str) -> None:
    """Log an action using rotating file handler."""
    if action_logger:
        action_logger.info(message)

def log_error(error_message: str, url: Optional[str] = None) -> None:
    """Log an error message using rotating file handler."""
    if error_logger:
        message = error_message
        if url and url not in error_message:
            message += f"\nURL: {url}"
        message += "\n" + "-"*50
        error_logger.error(message)

def log_url(url: str) -> None:
    """Log URL using rotating file handler."""
    if url_logger:
        url_logger.info(url)
