from __future__ import annotations
import time
import threading
from curl_cffi import requests


class RateLimiter:
    def __init__(self, max_requests: int = 10, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.tokens = float(max_requests)
        self.last_update = time.time()
        self.lock = threading.Lock()

    def _refill_tokens(self) -> None:
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.max_requests, self.tokens + (elapsed / self.time_window) * self.max_requests)
        self.last_update = now

    def wait_if_needed(self) -> None:
        with self.lock:
            self._refill_tokens()
            if self.tokens < 1:
                wait_time = (1 - self.tokens) * (self.time_window / self.max_requests)
                time.sleep(wait_time)
                self._refill_tokens()
            self.tokens -= 1

_CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_BROWSER_HEADERS = {
    "User-Agent": _CHROME_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

# Single session shared across all workers — preserves cf_clearance cookies
_session = requests.Session(impersonate="chrome120")
_session.headers.update(_BROWSER_HEADERS)

# Coordinates request rate across DownloadQueueWorker and MetadataRefreshWorker
global_rate_limiter = RateLimiter(max_requests=8, time_window=60)


def get_session() -> requests.Session:
    return _session
