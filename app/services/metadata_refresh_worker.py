from __future__ import annotations
import threading
import time
import traceback
from datetime import datetime
from typing import Optional
from flask import Flask

class MetadataRefreshWorker:
    """Background worker for processing metadata refresh queue"""

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
        self.thread = threading.Thread(target=self._worker_loop, daemon=True, name="MetadataRefreshWorker")
        self.thread.start()
    
    def _recover_stale_jobs(self):
        from app.models import MetadataRefreshQueueItem, db
        from .logger import log_action
        from datetime import datetime, timedelta
        
        with self.app.app_context():
            stale_cutoff = datetime.utcnow() - timedelta(minutes=10)
            
            stale_items = MetadataRefreshQueueItem.query.filter(
                MetadataRefreshQueueItem.status == 'processing',
                MetadataRefreshQueueItem.started_at < stale_cutoff
            ).all()
            
            if stale_items:
                log_action(f"[METADATA WORKER] Recovering {len(stale_items)} stale processing jobs")
                for item in stale_items:
                    item.status = 'pending'
                    item.started_at = None
                    item.progress_message = 'Reset from stale processing state'
                db.session.commit()
            
            recent_stuck = MetadataRefreshQueueItem.query.filter(
                MetadataRefreshQueueItem.status == 'processing'
            ).all()
            
            if recent_stuck:
                log_action(f"[METADATA WORKER] Found {len(recent_stuck)} items stuck in processing (likely from restart), resetting to pending")
                for item in recent_stuck:
                    item.status = 'pending'
                    item.started_at = None
                    item.progress_message = 'Reset from restart'
                db.session.commit()

    def stop(self):
        self.running = False
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=10)

    def _worker_loop(self):
        from .logger import log_action, log_error

        log_action("Metadata refresh worker started")

        while self.running and not self._stop_event.is_set():
            try:
                with self.app.app_context():
                    self._process_next_item()
            except Exception as e:
                log_error(f"Error in metadata refresh worker: {str(e)}\n{traceback.format_exc()}")

            self._stop_event.wait(self.poll_interval)

        log_action("Metadata refresh worker stopped")

    def _process_next_item(self):
        from app.models import MetadataRefreshQueueItem, db
        from .logger import log_action, log_error
        from sqlalchemy import select

        item = db.session.execute(
            select(MetadataRefreshQueueItem)
            .filter_by(status='pending')
            .order_by(MetadataRefreshQueueItem.created_at.asc())
            .limit(1)
        ).scalar_one_or_none()

        if not item:
            return

        item_id = item.id
        story_id = item.story_id
        
        log_action(f"Processing metadata refresh queue item {item_id} for story_id={story_id}")

        item.status = 'processing'
        item.started_at = datetime.utcnow()
        item.progress_message = 'Starting metadata refresh...'
        db.session.commit()

        try:
            self._refresh_metadata(item)

            item.status = 'completed'
            item.completed_at = datetime.utcnow()
            item.progress_message = 'Metadata refresh completed successfully'
            db.session.commit()

            log_action(f"Successfully completed metadata refresh queue item {item_id}")

        except Exception as e:
            error_msg = str(e)
            
            db.session.rollback()
            
            item = db.session.get(MetadataRefreshQueueItem, item_id)
            if not item:
                log_error(f"Failed to process metadata refresh queue item {item_id}: Item no longer exists")
                return
            
            log_error(f"Failed to process metadata refresh queue item {item_id}: {error_msg}\n{traceback.format_exc()}")

            item.retry_count += 1

            if item.retry_count >= item.max_retries:
                item.status = 'failed'
                item.error_message = f"Failed after {item.retry_count} attempts: {error_msg}"
                item.completed_at = datetime.utcnow()
                log_action(f"Metadata refresh queue item {item_id} failed permanently after {item.retry_count} retries")
            else:
                item.status = 'pending'
                item.error_message = f"Attempt {item.retry_count} failed: {error_msg}"
                log_action(f"Metadata refresh queue item {item_id} will be retried (attempt {item.retry_count + 1}/{item.max_retries})")

            db.session.commit()

    def _refresh_metadata(self, item: MetadataRefreshQueueItem):
        from app.models import db
        from .metadata_refresh_service import MetadataRefreshService
        from .logger import log_action

        item.progress_message = 'Fetching metadata from URL...'
        db.session.commit()

        service = MetadataRefreshService()
        refresh_result = service.refresh_metadata_from_url(item.story_id, item.url, method=item.method)

        if not refresh_result.get('success'):
            if refresh_result.get('duplicate_detected'):
                log_action(f"Story {item.story_id} excluded from auto-refresh: {refresh_result.get('message')}")
                return
            raise Exception(refresh_result.get('message', 'Failed to refresh metadata'))

        fields_changed = refresh_result.get('fields_changed', [])
        log_action(f"Successfully refreshed metadata for story_id={item.story_id} - Updated: {', '.join(fields_changed)}")
