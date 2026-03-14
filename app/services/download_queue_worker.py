from __future__ import annotations
import threading
import time
import traceback
from datetime import datetime
from typing import Optional
from flask import Flask
from app.services.metadata_refresh.rate_limiter import RateLimiter

class DownloadQueueWorker:
    """Background worker for processing download queue"""

    def __init__(self, app: Flask, poll_interval: int = 5):
        self.app = app
        self.poll_interval = poll_interval
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self._stop_event = threading.Event()
        # Conservative rate limit: max 5 downloads per 60 seconds to avoid
        # triggering Literotica's bot-detection between queued story downloads.
        self._rate_limiter = RateLimiter(max_requests=5, time_window=60)

    def start(self):
        """Start the background worker thread"""
        if self.thread and self.thread.is_alive():
            return

        self._recover_stale_jobs()

        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._worker_loop, daemon=True, name="DownloadQueueWorker")
        self.thread.start()

    def _recover_stale_jobs(self):
        """Reset jobs stuck in 'processing' state (from crashes/restarts)"""
        from app.models import DownloadQueueItem, db
        from datetime import datetime, timedelta

        with self.app.app_context():
            from .logger import log_action

            stale_cutoff = datetime.utcnow() - timedelta(minutes=10)
            stale_items = DownloadQueueItem.query.filter(
                DownloadQueueItem.status == 'processing',
                DownloadQueueItem.started_at < stale_cutoff
            ).all()

            if stale_items:
                log_action(f"[DOWNLOAD WORKER] Recovering {len(stale_items)} stale jobs")
                for item in stale_items:
                    item.status = 'pending'
                    item.started_at = None
                    item.progress_message = 'Reset from stale processing state'
                db.session.commit()

    def stop(self):
        """Stop the background worker thread"""
        self.running = False
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=10)

    def _worker_loop(self):
        """Main worker loop"""
        from .logger import log_action, log_error

        log_action("Download queue worker started")

        while self.running and not self._stop_event.is_set():
            try:
                with self.app.app_context():
                    self._process_next_item()
            except Exception as e:
                log_error(f"Error in download queue worker: {str(e)}\n{traceback.format_exc()}")

            self._stop_event.wait(self.poll_interval)

        log_action("Download queue worker stopped")

    def _process_next_item(self):
        """Process the next pending item in the queue"""
        from app.models import DownloadQueueItem, db
        from .logger import log_action, log_error
        from sqlalchemy import select

        item = db.session.execute(
            select(DownloadQueueItem)
            .filter_by(status='pending')
            .order_by(DownloadQueueItem.created_at.asc())
            .limit(1)
        ).scalar_one_or_none()

        if not item:
            return

        item_id = item.id
        log_action(f"Processing download queue item {item_id}: {item.url}")

        self._rate_limiter.wait_if_needed()

        item.status = 'processing'
        item.started_at = datetime.utcnow()
        item.progress_message = 'Starting download...'
        db.session.commit()

        try:
            self._download_and_save(item)

            item.status = 'completed'
            item.completed_at = datetime.utcnow()
            item.progress_message = 'Download completed successfully'
            db.session.commit()

            log_action(f"Successfully completed download queue item {item.id}")

            from .notifier import send_notification
            send_notification(
                f"Story Downloaded",
                f"'{item.title or 'Story'}' has been added to your library"
            )

        except Exception as e:
            error_msg = str(e)

            db.session.rollback()

            item = db.session.get(DownloadQueueItem, item_id)
            if not item:
                log_error(f"Failed to process download queue item {item_id}: Item no longer exists")
                return

            log_error(f"Failed to process download queue item {item_id}: {error_msg}\n{traceback.format_exc()}")

            item.retry_count += 1

            if item.retry_count >= item.max_retries:
                item.status = 'failed'
                item.error_message = f"Failed after {item.retry_count} attempts: {error_msg}"
                item.completed_at = datetime.utcnow()
                log_action(f"Download queue item {item_id} failed permanently after {item.retry_count} retries")
            else:
                item.status = 'pending'
                item.error_message = f"Attempt {item.retry_count} failed: {error_msg}"
                log_action(f"Download queue item {item_id} will be retried (attempt {item.retry_count + 1}/{item.max_retries})")

            db.session.commit()

    def _download_and_save(self, item: DownloadQueueItem):
        """Download story and save to database"""
        from app.models import db
        from .story_downloader import download_story
        from .logger import log_action, log_error

        item.progress_message = 'Downloading story content...'
        db.session.commit()

        story_data = download_story(item.url)
        story_content, title, author, category, tags, author_url, page_count, series_url, story_description = story_data

        if not story_content or not title:
            raise Exception("Failed to download story content or extract metadata")

        item.title = title
        item.author = author
        item.category = category
        item.set_tags(tags)
        item.total_pages = page_count
        item.downloaded_pages = page_count
        db.session.commit()

        item.progress_message = 'Creating files...'
        db.session.commit()

        from .story_processor import _create_story_files
        result = _create_story_files(
            story_content=story_content,
            story_title=title,
            story_author=author,
            story_category=category,
            story_tags=tags,
            source_url=item.url,
            author_url=author_url,
            page_count=page_count,
            formats=item.get_formats(),
            series_url=series_url,
            story_description=story_description
        )

        if not result.get('success'):
            raise Exception(result.get('message', 'Failed to create story files'))

        from app.models import Story
        story = Story.query.filter_by(literotica_url=item.url).first()
        if story:
            item.story_id = story.id
            db.session.commit()

        log_action(f"Successfully saved story '{title}' from queue item {item.id}")
