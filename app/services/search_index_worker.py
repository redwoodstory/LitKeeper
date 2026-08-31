from __future__ import annotations

import threading
import traceback
from typing import Optional

from flask import Flask


class SearchIndexWorker:
    """Periodically re-indexes stories whose body text has changed.

    The ~10 code paths that write story JSON don't all funnel through one place,
    so rather than hook every one, this sweep reconciles the FTS index against
    ``stories.content_indexed_at`` on an interval.
    """

    def __init__(self, app: Flask, poll_interval: int = 300, batch_size: int = 100):
        self.app = app
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self._stop_event = threading.Event()

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True, name="SearchIndexWorker")
        self.thread.start()

    def stop(self):
        self.running = False
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=10)

    def _loop(self):
        from .logger import log_action, log_error

        while self.running and not self._stop_event.is_set():
            try:
                with self.app.app_context():
                    from . import search_index
                    if search_index.fts5_available():
                        result = search_index.reindex_stale(limit=self.batch_size)
                        if result.get('indexed') or result.get('pruned'):
                            log_action(
                                f"[SEARCH INDEX] reindexed {result['indexed']}, "
                                f"pruned {result['pruned']}, failed {result['failed']}"
                            )
            except Exception as e:
                log_error(f"Error in search index worker: {e}\n{traceback.format_exc()}")

            self._stop_event.wait(self.poll_interval)
