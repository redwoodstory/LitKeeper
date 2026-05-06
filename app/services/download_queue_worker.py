from __future__ import annotations
import os
import threading
import time
import traceback
from datetime import datetime, timedelta
from typing import Optional
from flask import Flask
from app.services.metadata_refresh.rate_limiter import RateLimiter

DEFAULT_MAX_DAILY_DOWNLOADS = 25

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
        self._last_rate_limit_reset_date: Optional[str] = None

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
            from .logger import log_action, log_error
            try:
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
            except Exception as e:
                db.session.rollback()
                log_error(f"[DOWNLOAD WORKER] Could not recover stale jobs (migrations pending?): {e}")

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

    def _get_daily_cap(self) -> int:
        try:
            return int(os.environ['MAX_DAILY_DOWNLOADS'])
        except (KeyError, ValueError):
            return DEFAULT_MAX_DAILY_DOWNLOADS

    def _reset_rate_limited_items(self):
        """Requeue items that were rate-limited and are now in a new UTC day. Runs at most once per day."""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        if self._last_rate_limit_reset_date == today:
            return
        self._last_rate_limit_reset_date = today

        from app.models import DownloadQueueItem, db
        from .logger import log_action
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        rate_limited = DownloadQueueItem.query.filter(
            DownloadQueueItem.status == 'rate_limited',
            DownloadQueueItem.completed_at < today_start
        ).all()
        if rate_limited:
            log_action(f"[DOWNLOAD WORKER] Resetting {len(rate_limited)} rate-limited items for new day")
            for it in rate_limited:
                it.status = 'pending'
                it.progress_message = None
                it.completed_at = None
            db.session.commit()

    def _daily_downloads_today(self) -> int:
        """Count completed downloads since midnight UTC."""
        from app.models import DownloadQueueItem
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return DownloadQueueItem.query.filter(
            DownloadQueueItem.status == 'completed',
            DownloadQueueItem.completed_at >= today_start
        ).count()

    def _process_next_item(self):
        """Process the next pending item in the queue"""
        from app.models import DownloadQueueItem, db
        from .logger import log_action, log_error
        from sqlalchemy import select

        self._reset_rate_limited_items()

        now = datetime.utcnow()
        item = db.session.execute(
            select(DownloadQueueItem)
            .filter(
                DownloadQueueItem.status == 'pending',
                (DownloadQueueItem.scheduled_after == None) | (DownloadQueueItem.scheduled_after <= now)
            )
            .order_by(DownloadQueueItem.created_at.asc())
            .limit(1)
        ).scalar_one_or_none()

        if not item:
            return

        item_id = item.id

        daily_cap = self._get_daily_cap()
        if self._daily_downloads_today() >= daily_cap:
            log_action(f"[DOWNLOAD WORKER] Daily cap of {daily_cap} reached — marking pending items as rate_limited")
            pending = DownloadQueueItem.query.filter(
                DownloadQueueItem.status == 'pending',
                (DownloadQueueItem.scheduled_after == None) | (DownloadQueueItem.scheduled_after <= now)
            ).all()
            for it in pending:
                it.status = 'rate_limited'
                it.progress_message = f'Daily download limit of {daily_cap} reached. Resumes tomorrow.'
                it.completed_at = datetime.utcnow()
            db.session.commit()
            return

        log_action(f"Processing download queue item {item_id}: {item.url} (job_type={item.job_type})")

        self._rate_limiter.wait_if_needed()

        item.status = 'processing'
        item.started_at = datetime.utcnow()
        item.progress_message = 'Starting download...'
        db.session.commit()

        try:
            downloaded = True
            if item.job_type == 'author':
                self._process_author_scan(item)
            elif item.job_type == 'multi':
                downloaded = self._download_and_save_multi(item)
            else:
                downloaded = self._download_and_save(item)

            if item.job_type != 'author' and not downloaded:
                item.status = 'skipped'
            else:
                item.status = 'completed'
                item.progress_message = 'Download completed successfully'
            item.completed_at = datetime.utcnow()
            db.session.commit()

            log_action(f"Successfully completed download queue item {item.id}")

            if item.job_type != 'author' and downloaded:
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

    def _download_and_save(self, item):
        """Download a single story URL and save to database.

        Returns True if the story was downloaded, False if skipped as already seen.
        """
        from app.models import db, SeenLiteroticaUrl
        from .story_downloader import download_story
        from .logger import log_action, log_error

        if item.job_type != 'redownload' and SeenLiteroticaUrl.query.filter_by(url=item.url).first():
            log_action(f"Skipping already-seen URL: {item.url}")
            item.progress_message = 'Skipped: already downloaded as part of a series'
            db.session.commit()
            return False

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

        # Redownloads should always regenerate both formats to keep the library complete.
        formats = item.get_formats()
        if item.job_type == 'redownload':
            formats = ['epub', 'html']

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
            formats=formats,
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
            # Ensure any missing format is queued for generation after a download.
            self._ensure_complete_formats(story)

        log_action(f"Successfully saved story '{title}' from queue item {item.id}")
        return True

    def _download_and_save_multi(self, item):
        """Download and combine multiple URLs into a single story."""
        from app.models import db
        from .story_downloader import download_and_combine_stories
        from .logger import log_action, log_error

        extra = item.get_extra_urls()
        all_urls = [item.url] + extra

        item.progress_message = f'Downloading and combining {len(all_urls)} stories...'
        db.session.commit()

        story_data = download_and_combine_stories(all_urls)
        story_content, title, author, category, tags, author_url, page_count, series_url, story_description = story_data

        if not story_content or not title:
            raise Exception("Failed to combine stories")

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
            raise Exception(result.get('message', 'Failed to create combined story files'))

        from app.models import Story, StorySource
        story = Story.query.filter_by(literotica_url=item.url).first()
        if story:
            story.is_combined = True
            story.chapter_count = len(all_urls)
            story.auto_refresh_excluded = True
            story.auto_refresh_exclusion_reason = "User-created combined story — cannot be auto-refreshed"
            story.auto_refresh_exclusion_type = 'combined'
            story.auto_update_enabled = False
            item.story_id = story.id
            story.sources = [StorySource(url=url, position=pos) for pos, url in enumerate(all_urls)]
            db.session.commit()
            self._ensure_complete_formats(story)

        log_action(f"Successfully saved combined story '{title}' from queue item {item.id}")
        return True

    def _ensure_complete_formats(self, story):
        """After a download completes, queue any missing format generation jobs."""
        import os as _os
        from app.models import StoryFormat, FormatQueueItem
        from app.models.format_queue import FormatQueueItem as _FQI
        from app.models.base import db
        from app.services.story_processor import link_story_formats
        from app.services.logger import log_action
        from app.utils import story_epub_path, story_json_path

        try:
            link_story_formats(story)

            epub_fmt = StoryFormat.query.filter_by(story_id=story.id, format_type='epub').first()
            json_fmt = StoryFormat.query.filter_by(story_id=story.id, format_type='json').first()
            epub_ok = epub_fmt and _os.path.exists(epub_fmt.file_path)
            json_ok = json_fmt and _os.path.exists(json_fmt.file_path)

            queued = 0
            if not epub_ok:
                canonical = story_epub_path(story.id, story.filename_base)
                if _os.path.exists(canonical):
                    # File exists but no DB record — link_story_formats already handled it
                    pass
                elif not _FQI.query.filter_by(story_id=story.id, job_type='generate_epub', status='pending').first():
                    db.session.add(_FQI(story_id=story.id, job_type='generate_epub', method='auto'))
                    queued += 1

            if not json_ok:
                canonical = story_json_path(story.id, story.filename_base)
                if _os.path.exists(canonical):
                    pass
                elif not _FQI.query.filter_by(story_id=story.id, job_type='generate_json', status='pending').first():
                    db.session.add(_FQI(story_id=story.id, job_type='generate_json', method='auto'))
                    queued += 1

            if queued:
                db.session.commit()
                log_action(f"[DOWNLOAD WORKER] Queued {queued} missing format generation job(s) for story {story.id}")
        except Exception:
            db.session.rollback()

    def _process_author_scan(self, item):
        """Scan an author URL and enqueue each discovered story/series as an individual 'single' queue item."""
        from app.models import DownloadQueueItem, Author, db
        from .author_scraper import AuthorScraper
        from .logger import log_action, log_error
        import json

        author_url = item.url
        item.progress_message = f'Scanning author page...'
        db.session.commit()

        scraper = AuthorScraper()
        stories = scraper.scrape_story_urls(author_url)

        if not stories:
            log_action(f"[AuthorScan] Author page loaded but no stories found: {author_url}")
            item.status = 'completed'
            item.progress_message = 'Author page scanned — no stories found'
            item.completed_at = datetime.utcnow()
            db.session.commit()
            return

        item.progress_message = f'Found {len(stories)} stories — queuing downloads...'
        db.session.commit()

        # Update known_story_urls so background watch can detect truly new stories later.
        all_urls = [s['url'] for s in stories]
        author_obj = Author.query.filter_by(literotica_url=author_url).first()
        if author_obj:
            author_obj.set_known_story_urls(all_urls)
            author_obj.last_watch_check_at = datetime.utcnow()
            db.session.commit()

        formats = item.get_formats()
        enqueued = 0

        for story in stories:
            story_url = story['url']

            # Skip if already active in the queue
            active = DownloadQueueItem.query.filter(
                DownloadQueueItem.url == story_url,
                DownloadQueueItem.status.in_(['pending', 'processing', 'rate_limited'])
            ).first()
            if active:
                continue

            # Skip if this URL has already been consumed (as a standalone story
            # or as a chapter inside a previously downloaded series).
            from app.models import SeenLiteroticaUrl
            if SeenLiteroticaUrl.query.filter_by(url=story_url).first():
                continue

            child = DownloadQueueItem(
                url=story_url,
                formats=json.dumps(formats),
                status='pending',
                job_type='single',
                title=story.get('title'),
                author=item.author,
                progress_message='Queued from author scan'
            )
            db.session.add(child)
            enqueued += 1

        db.session.commit()
        log_action(f"[AuthorScan] Queued {enqueued} new stories from {author_url}")
        item.title = item.title or f'Author scan: {author_url}'
        item.progress_message = f'Queued {enqueued} new stories for download'
        db.session.commit()
