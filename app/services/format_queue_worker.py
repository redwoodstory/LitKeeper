from __future__ import annotations
import threading
import time
import traceback
from datetime import datetime, timedelta
from typing import Optional
from flask import Flask


class FormatQueueWorker:
    """Background worker that processes FormatQueueItem jobs one at a time."""

    def __init__(self, app: Flask, poll_interval: int = 5):
        self.app = app
        self.poll_interval = poll_interval
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self._stop_event = threading.Event()

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self._recover_stale_jobs()
        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._worker_loop, daemon=True, name="FormatQueueWorker")
        self.thread.start()

    def _recover_stale_jobs(self):
        from app.models import db
        from app.models.format_queue import FormatQueueItem
        with self.app.app_context():
            from .logger import log_action
            stale_cutoff = datetime.utcnow() - timedelta(minutes=15)
            stale = FormatQueueItem.query.filter(
                FormatQueueItem.status == 'processing',
                FormatQueueItem.started_at < stale_cutoff
            ).all()
            if stale:
                log_action(f"[FORMAT WORKER] Recovering {len(stale)} stale format jobs")
                for item in stale:
                    item.status = 'pending'
                    item.started_at = None
                    item.progress_message = 'Reset from stale processing state'
                db.session.commit()

    def stop(self):
        self.running = False
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=10)

    def _worker_loop(self):
        from .logger import log_action, log_error
        log_action("Format queue worker started")
        while self.running and not self._stop_event.is_set():
            try:
                with self.app.app_context():
                    self._process_next_item()
            except Exception as e:
                log_error(f"Error in format queue worker: {str(e)}\n{traceback.format_exc()}")
            self._stop_event.wait(self.poll_interval)
        log_action("Format queue worker stopped")

    def _process_next_item(self):
        from app.models import db
        from app.models.format_queue import FormatQueueItem
        from sqlalchemy import select
        from .logger import log_action, log_error

        item = db.session.execute(
            select(FormatQueueItem)
            .filter_by(status='pending')
            .order_by(FormatQueueItem.created_at.asc())
            .limit(1)
        ).scalar_one_or_none()

        if not item:
            return

        item_id = item.id
        log_action(f"Processing format queue item {item_id}: {item.job_type} for story {item.story_id}")

        item.status = 'processing'
        item.started_at = datetime.utcnow()
        item.progress_message = 'Starting...'
        db.session.commit()

        try:
            self._run_job(item)
            item.status = 'completed'
            item.completed_at = datetime.utcnow()
            item.progress_message = 'Done'
            db.session.commit()
            log_action(f"Format queue item {item_id} completed")
        except Exception as e:
            db.session.rollback()
            item = db.session.get(FormatQueueItem, item_id)
            if item:
                item.status = 'failed'
                item.error_message = str(e)
                item.completed_at = datetime.utcnow()
                db.session.commit()
            log_error(f"Format queue item {item_id} failed: {str(e)}\n{traceback.format_exc()}")

    def _run_job(self, item):
        from app.services.format_generator import FormatGeneratorService
        from .logger import log_action

        service = FormatGeneratorService()

        if item.job_type == 'generate_epub':
            item.progress_message = 'Generating EPUB from local data...'
            from app.models.base import db as _db
            _db.session.commit()
            result = service.generate_epub_from_json(item.story_id)

        elif item.job_type == 'generate_html':
            item.progress_message = 'Downloading from Literotica...'
            from app.models.base import db as _db
            _db.session.commit()
            result = service.generate_html_from_url(item.story_id)

        elif item.job_type == 'generate_html_with_metadata':
            item.progress_message = 'Downloading from Literotica...'
            from app.models.base import db as _db
            _db.session.commit()
            result = service.generate_html_with_metadata(item.story_id, item.url, item.method or 'manual')

        else:
            raise ValueError(f"Unknown job_type: {item.job_type}")

        if not result.get('success'):
            raise Exception(result.get('message', 'Format generation failed'))

        log_action(f"Format job {item.id} ({item.job_type}) succeeded for story {item.story_id}")
