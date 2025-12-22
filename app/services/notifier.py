from __future__ import annotations
import os
import traceback
from .logger import log_error

NOTIFICATION_URLS_RAW = os.getenv('NOTIFICATION_URLS', '')
NOTIFICATION_URLS = NOTIFICATION_URLS_RAW.split(',')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
    telegram_url = f"tgram://{TELEGRAM_BOT_TOKEN}/{TELEGRAM_CHAT_ID}"
    if telegram_url not in NOTIFICATION_URLS:
        NOTIFICATION_URLS.append(telegram_url)

ENABLE_NOTIFICATIONS = bool(NOTIFICATION_URLS and NOTIFICATION_URLS[0])

def _initialize_logging() -> None:
    """Initialize startup logging for notification configuration."""
    from .logger import _log_startup_info
    _log_startup_info()

_initialize_logging()

def send_notification(message: str, is_error: bool = False) -> None:
    """Send a notification using Apprise to configured notification services."""
    if not ENABLE_NOTIFICATIONS:
        return

    try:
        import apprise

        apobj = apprise.Apprise()

        added_count = 0
        for i, url in enumerate(NOTIFICATION_URLS):
            url = url.strip()
            if url:
                if apobj.add(url):
                    added_count += 1
                else:
                    url_preview = url[:50] + "..." if len(url) > 50 else url
                    log_error(f"Failed to add notification URL {i+1}: {url_preview}")

        if added_count == 0:
            log_error("No notification URLs were successfully added to Apprise")
            return

        icon = "❌" if is_error else "✅"
        formatted_message = f"{icon} {message}"

        if apobj.notify(body=formatted_message):
            pass
        else:
            log_error("Failed to send notification - apobj.notify() returned False")
    except Exception as e:
        log_error(f"Error sending notification: {str(e)}\n{traceback.format_exc()}")
