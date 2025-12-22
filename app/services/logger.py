from __future__ import annotations
import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

ENABLE_ACTION_LOG = os.getenv('ENABLE_ACTION_LOG', 'true').lower() == 'true'
ENABLE_ERROR_LOG = os.getenv('ENABLE_ERROR_LOG', 'true').lower() == 'true'
ENABLE_URL_LOG = os.getenv('ENABLE_URL_LOG', 'true').lower() == 'true'

log_directory = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "logs")
os.makedirs(log_directory, exist_ok=True)

def _setup_logger(name: str, log_file: str, level: int = logging.INFO) -> logging.Logger:
    """Configure a logger with rotating file handler (10MB max, 5 backups)."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = RotatingFileHandler(
            os.path.join(log_directory, log_file),
            maxBytes=10 * 1024 * 1024,
            backupCount=5
        )
        formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger

action_logger = _setup_logger('litkeeper.action', 'log.txt') if ENABLE_ACTION_LOG else None
error_logger = _setup_logger('litkeeper.error', 'error_log.txt', logging.ERROR) if ENABLE_ERROR_LOG else None
url_logger = _setup_logger('litkeeper.url', 'url_log.txt') if ENABLE_URL_LOG else None

def _log_startup_info() -> None:
    """Log startup notification configuration information."""
    if action_logger:
        from .notifier import NOTIFICATION_URLS_RAW, NOTIFICATION_URLS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ENABLE_NOTIFICATIONS
        action_logger.info("[STARTUP] Notification configuration loaded")
        action_logger.info(f"[STARTUP] NOTIFICATION_URLS_RAW: '{NOTIFICATION_URLS_RAW[:100]}...'")
        action_logger.info(f"[STARTUP] NOTIFICATION_URLS_RAW length: {len(NOTIFICATION_URLS_RAW)}")
        action_logger.info(f"[STARTUP] NOTIFICATION_URLS after split: {len(NOTIFICATION_URLS)} URLs")
        for i, url in enumerate(NOTIFICATION_URLS):
            url_preview = url[:50] + "..." if len(url) > 50 else url
            action_logger.info(f"[STARTUP] URL {i+1}: '{url_preview}' (length: {len(url)})")
        action_logger.info(f"[STARTUP] ENABLE_NOTIFICATIONS: {ENABLE_NOTIFICATIONS}")
        action_logger.info(f"[STARTUP] TELEGRAM_BOT_TOKEN: {'SET' if TELEGRAM_BOT_TOKEN else 'NOT SET'}")
        action_logger.info(f"[STARTUP] TELEGRAM_CHAT_ID: {'SET' if TELEGRAM_CHAT_ID else 'NOT SET'}")

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
