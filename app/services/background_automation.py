from __future__ import annotations
import threading
import time
import random
from datetime import datetime
from typing import Optional
from app.services.logger import log_action, log_error
from sqlalchemy import or_
from app.models import db, Story


class BackgroundAutomation:
    """
    Background service that automatically:
    1. Adds new stories from filesystem to library
    2. Auto-refreshes metadata for stories with 100% confidence matches
    """
    
    def __init__(self, app):
        self.app = app
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.check_interval = 300
        self.last_run_time: Optional[datetime] = None
        self._processing_lock = threading.Lock()
        self._is_processing = False
        self.has_completed_first_run = False

    @property
    def is_processing(self) -> bool:
        with self._processing_lock:
            return self._is_processing

    @is_processing.setter
    def is_processing(self, value: bool):
        with self._processing_lock:
            self._is_processing = value
    
    def start(self):
        if self.running:
            log_action("[AUTOMATION] Background automation already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        log_action("[AUTOMATION] Background automation started")
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        log_action("[AUTOMATION] Background automation stopped")
    
    def trigger_immediate_run(self):
        """
        Trigger an immediate automation run in a separate thread.
        This allows on-demand processing without blocking the request.
        """
        with self._processing_lock:
            if self._is_processing:
                log_action("[AUTOMATION] Already processing, skipping immediate run")
                return
            self._is_processing = True

        def run_once():
            try:
                self.last_run_time = datetime.utcnow()
                log_action("[AUTOMATION] Running immediate automation cycle")

                with self.app.app_context():
                    self._heal_exclusion_inconsistencies()
                    self._heal_missing_formats()
                    self._auto_add_stories()
                    self._auto_refresh_metadata()
                    self._cleanup_orphaned_covers()

                self.is_processing = False
                self.has_completed_first_run = True
            except Exception as e:
                log_error(f"[AUTOMATION] Error in immediate automation run: {str(e)}")
                self.is_processing = False
                self.has_completed_first_run = True

        thread = threading.Thread(target=run_once, daemon=True)
        thread.start()
    
    def _run_loop(self):
        time.sleep(5)

        with self.app.app_context():
            self._backfill_missing_descriptions()

        while self.running:
            try:
                self.is_processing = True
                self.last_run_time = datetime.utcnow()

                with self.app.app_context():
                    self._heal_exclusion_inconsistencies()
                    self._heal_missing_formats()
                    self._auto_add_stories()
                    self._auto_refresh_metadata()
                    self._cleanup_orphaned_covers()

                self.is_processing = False
                self.has_completed_first_run = True
            except Exception as e:
                log_error(f"[AUTOMATION] Error in background automation: {str(e)}")
                self.is_processing = False
                self.has_completed_first_run = True

            for _ in range(self.check_interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def _heal_missing_formats(self):
        """Repair stale StoryFormat paths and queue generation of missing EPUB/JSON formats."""
        try:
            import os
            from app.models import Story, StoryFormat, FormatQueueItem
            from app.models.base import db
            from app.services.story_processor import link_story_formats
            from app.services.migration.migrate_covers_to_id_prefix import migrate_covers_to_id_prefix

            # Rename any legacy cover files ({filename_base}.jpg → {id}_{filename_base}.jpg)
            migrate_covers_to_id_prefix()

            stories = Story.query.all()
            paths_fixed = 0
            epub_queued = 0
            json_queued = 0

            for story in stories:
                # Heal if formats are missing entirely or any recorded path no longer exists
                needs_link = not story.formats or any(not os.path.exists(f.file_path) for f in story.formats)
                if needs_link:
                    link_story_formats(story)
                    paths_fixed += 1

                json_fmt = StoryFormat.query.filter_by(story_id=story.id, format_type='json').first()
                epub_fmt = StoryFormat.query.filter_by(story_id=story.id, format_type='epub').first()
                json_ok = json_fmt and os.path.exists(json_fmt.file_path)
                epub_ok = epub_fmt and os.path.exists(epub_fmt.file_path)

                if json_ok and not epub_ok:
                    if not FormatQueueItem.query.filter_by(story_id=story.id, job_type='generate_epub', status='pending').first():
                        db.session.add(FormatQueueItem(story_id=story.id, job_type='generate_epub', method='auto'))
                        epub_queued += 1

                if epub_ok and not json_ok:
                    if not FormatQueueItem.query.filter_by(story_id=story.id, job_type='generate_json', status='pending').first():
                        db.session.add(FormatQueueItem(story_id=story.id, job_type='generate_json', method='auto'))
                        json_queued += 1

            if epub_queued or json_queued:
                db.session.commit()

            log_action(f"[AUTOMATION] Format heal: {paths_fixed} path(s) repaired, {epub_queued} EPUB + {json_queued} JSON job(s) queued.")

        except Exception as e:
            db.session.rollback()
            log_error(f"[AUTOMATION] Error in format self-heal: {str(e)}")

    def _heal_exclusion_inconsistencies(self):
        """
        Heal inconsistent exclusion state:
        1. is_combined=True without exclusion fields set -> populate them
        2. auto_refresh_excluded=True with null reason -> set excluded=False
        3. auto_refresh_excluded=True with auto_update_enabled=True -> set auto_update_enabled=False
        """
        try:
            from app.models import Story, db

            # Fix 1: Combined stories missing exclusion fields (backfill for existing library)
            untagged_combined = Story.query.filter(
                Story.is_combined == True,
                Story.auto_refresh_excluded == False
            ).all()
            for story in untagged_combined:
                story.auto_refresh_excluded = True
                story.auto_refresh_exclusion_reason = "User-created combined story — cannot be auto-refreshed"
                story.auto_refresh_exclusion_type = 'combined'
                story.auto_update_enabled = False
                log_action(f"[AUTOMATION] Flagged combined story '{story.title}' as excluded")
            if untagged_combined:
                db.session.commit()

            # Fix 2: Excluded without a reason
            orphaned = Story.query.filter(
                Story.auto_refresh_excluded == True,
                Story.auto_refresh_exclusion_reason.is_(None)
            ).all()
            for story in orphaned:
                story.auto_refresh_excluded = False
                story.auto_refresh_exclusion_type = None
                log_action(f"[AUTOMATION] Healed orphaned exclusion for '{story.title}' (no reason)")
            if orphaned:
                db.session.commit()

            # Fix 3: Excluded but still marked for auto-update
            mismatched = Story.query.filter(
                Story.auto_refresh_excluded == True,
                Story.auto_update_enabled == True
            ).all()
            for story in mismatched:
                story.auto_update_enabled = False
                log_action(f"[AUTOMATION] Healed mismatch for '{story.title}' (excluded story should not auto-update)")
            if mismatched:
                db.session.commit()

            total = len(untagged_combined) + len(orphaned) + len(mismatched)
            if total:
                log_action(f"[AUTOMATION] Exclusion heal complete: {len(untagged_combined)} combined, {len(orphaned)} orphaned, {len(mismatched)} mismatched")

        except Exception as e:
            db.session.rollback()
            log_error(f"[AUTOMATION] Error healing exclusions: {str(e)}")

    def _auto_add_stories(self):
        try:
            from app.services.migration.sync_checker import SyncChecker

            sync_checker = SyncChecker()
            sync_status = sync_checker.check_sync()

            orphaned_count = sync_status['orphaned_files_count']
            duplicate_count = sync_status.get('duplicate_files_count', 0)

            log_action(f"[AUTOMATION] Sync status: {orphaned_count} orphaned files, {duplicate_count} duplicates")

            if orphaned_count > 0:
                log_action(f"[AUTOMATION] Found {orphaned_count} new stories in filesystem, adding to library...")

                added_count = sync_checker.add_orphaned_files()

                if added_count > 0:
                    log_action(f"[AUTOMATION] Successfully added {added_count} stories to library")
                else:
                    log_action(f"[AUTOMATION] No new stories added (duplicates or errors)")
            else:
                log_action("[AUTOMATION] No orphaned files to add")

            if duplicate_count > 0:
                removed = sync_checker.cleanup_confirmed_duplicates()
                if removed:
                    log_action(f"[AUTOMATION] Removed {removed} confirmed-duplicate file group(s) from filesystem.")

        except Exception as e:
            log_error(f"[AUTOMATION] Error auto-adding stories: {str(e)}")
    
    def _auto_refresh_metadata(self):
        try:
            from app.services.metadata_refresh_service import MetadataRefreshService
            from app.models import MetadataRefreshQueueItem
            
            stories_missing_metadata = Story.query.filter(
                Story.literotica_url.is_(None),
                Story.auto_refresh_excluded == False
            ).all()
            
            excluded_stories = Story.query.filter(
                Story.literotica_url.is_(None),
                Story.auto_refresh_excluded == True
            ).count()
            
            if not stories_missing_metadata:
                if excluded_stories > 0:
                    log_action(f"[AUTOMATION] No stories to check ({excluded_stories} excluded from auto-refresh)")
                else:
                    log_action("[AUTOMATION] No stories missing metadata")
                return
            
            log_action(f"[AUTOMATION] Found {len(stories_missing_metadata)} stories missing metadata, checking for auto-matches...")
            if excluded_stories > 0:
                log_action(f"[AUTOMATION] ({excluded_stories} stories excluded from auto-refresh)")
            
            queued_count = 0
            processed_count = 0
            
            for story in stories_missing_metadata:
                try:
                    processed_count += 1
                    log_action(f"[AUTOMATION] Checking story {processed_count}/{len(stories_missing_metadata)}: '{story.title}'")
                    
                    existing_job = MetadataRefreshQueueItem.query.filter(
                        MetadataRefreshQueueItem.story_id == story.id,
                        MetadataRefreshQueueItem.status.in_(['pending', 'processing'])
                    ).first()
                    
                    if existing_job:
                        log_action(f"[AUTOMATION] Skipping '{story.title}' - already queued")
                        continue
                    
                    service = MetadataRefreshService()
                    
                    log_action(f"[AUTOMATION] Searching Literotica for: title='{story.title}', author='{story.author.name}'")
                    
                    search_result = service.search_for_story(story.id)
                    time.sleep(random.randint(10, 15))

                    if not search_result.get('success'):
                        exclusion_reason = f"No matches found on Literotica for '{story.title}' by {story.author.name}"
                        log_action(f"[AUTOMATION] {exclusion_reason} - marking as excluded")
                        
                        story.auto_refresh_excluded = True
                        story.auto_refresh_exclusion_reason = exclusion_reason
                        story.auto_refresh_exclusion_type = 'no_match'
                        db.session.commit()
                        continue
                    
                    results = search_result.get('results', [])
                    log_action(f"[AUTOMATION] Found {len(results)} potential matches for '{story.title}':")
                    for idx, result in enumerate(results[:5], 1):
                        log_action(f"[AUTOMATION]   {idx}. '{result['title']}' by {result['author']} - {result['confidence']:.1%} confidence")
                        log_action(f"[AUTOMATION]      URL: {result['url']}")
                    
                    if not search_result.get('auto_match'):
                        best = search_result.get('best_match')
                        if best:
                            exclusion_reason = f"Best match only {best['confidence']:.1%} confident (need ≥85% for auto-match)"
                            log_action(f"[AUTOMATION] {exclusion_reason} - marking as excluded")
                        else:
                            exclusion_reason = f"No confident match found on Literotica for '{story.title}' by {story.author.name}"
                            log_action(f"[AUTOMATION] {exclusion_reason} - marking as excluded")
                        
                        story.auto_refresh_excluded = True
                        story.auto_refresh_exclusion_reason = exclusion_reason
                        story.auto_refresh_exclusion_type = 'low_confidence'
                        db.session.commit()
                        continue
                    
                    best_match = search_result.get('best_match')
                    if not best_match:
                        continue
                    
                    confidence = best_match.get('confidence', 0.0)
                    log_action(f"[AUTOMATION] Found auto-match with {confidence:.1%} confidence")
                    
                    if confidence >= 0.85:
                        url = best_match['url']
                        log_action(f"[AUTOMATION] ✓ Queuing metadata refresh for '{story.title}' (100% match: {url})")
                        
                        queue_item = MetadataRefreshQueueItem(
                            story_id=story.id,
                            url=url,
                            method='auto',
                            status='pending'
                        )
                        db.session.add(queue_item)
                        db.session.commit()
                        
                        queued_count += 1

                except Exception as e:
                    db.session.rollback()
                    log_error(f"[AUTOMATION] Error processing story '{story.title}': {str(e)}")
                    continue
            
            if queued_count > 0:
                log_action(f"[AUTOMATION] Queued {queued_count} metadata refresh jobs for stories with 100% matches")
            else:
                log_action(f"[AUTOMATION] Completed checking {len(stories_missing_metadata)} stories - no 100% matches found")
        
        except Exception as e:
            db.session.rollback()
            log_error(f"[AUTOMATION] Error auto-refreshing metadata: {str(e)}")

    def _cleanup_orphaned_covers(self):
        """Remove cover images on disk only when no EPUB, JSON, or DB record references them."""
        try:
            import os
            import re
            from app.utils import get_cover_directory, get_epub_directory, get_html_directory
            from app.models import Story

            cover_dir = get_cover_directory()
            if not os.path.exists(cover_dir):
                return

            epub_dir = get_epub_directory()
            html_dir = get_html_directory()

            db_expected = {f"{s.id}_{s.filename_base}.jpg" for s in Story.query.all()}

            # Build sets of filename_bases present on disk so we can cross-check covers
            # against story files even when the DB record is missing.
            epub_bases = set()
            if os.path.exists(epub_dir):
                for name in os.listdir(epub_dir):
                    if name.endswith('.epub'):
                        base = re.sub(r'^\d+_', '', name[:-5])  # strip leading id_ prefix
                        epub_bases.add(base)
                        epub_bases.add(name[:-5])  # also keep the raw stem for legacy names

            json_bases = set()
            if os.path.exists(html_dir):
                for name in os.listdir(html_dir):
                    if name.endswith('.json'):
                        base = re.sub(r'^\d+_', '', name[:-5])
                        json_bases.add(base)
                        json_bases.add(name[:-5])

            removed = 0
            for filename in os.listdir(cover_dir):
                if not filename.endswith('.jpg') or filename in db_expected:
                    continue

                # Extract filename_base from cover (pattern: {id}_{filename_base}.jpg or {filename_base}.jpg)
                stem = filename[:-4]
                cover_base = re.sub(r'^\d+_', '', stem)

                if cover_base in epub_bases or cover_base in json_bases or stem in epub_bases or stem in json_bases:
                    log_action(f"[AUTOMATION] Skipping cover with matching story file on disk: {filename}")
                    continue

                try:
                    os.remove(os.path.join(cover_dir, filename))
                    removed += 1
                    log_action(f"[AUTOMATION] Removed orphaned cover: {filename}")
                except Exception as e:
                    log_error(f"[AUTOMATION] Failed to remove orphaned cover {filename}: {e}")

            if removed:
                log_action(f"[AUTOMATION] Cleaned up {removed} orphaned cover image(s).")

        except Exception as e:
            log_error(f"[AUTOMATION] Error cleaning orphaned covers: {e}")

    def _backfill_missing_descriptions(self):
        """One-time startup backfill: fetch descriptions for auto-update stories that are missing one."""
        try:
            from app.services.story_downloader import fetch_story_metadata
            from app.services.metadata_refresh.rate_limiter import RateLimiter

            stories = Story.query.filter(
                Story.auto_update_enabled == True,
                Story.literotica_url.isnot(None),
                or_(Story.description.is_(None), Story.description == '')
            ).all()

            if not stories:
                return

            log_action(f"[AUTOMATION] Startup description backfill: {len(stories)} stories missing descriptions")
            rate_limiter = RateLimiter(max_requests=5, time_window=60)

            updated = 0
            for story in stories:
                if not self.running:
                    break
                try:
                    rate_limiter.wait_if_needed()
                    metadata = fetch_story_metadata(story.literotica_url)
                    if not metadata:
                        continue
                    changed = False
                    description = metadata.get('description')
                    if description:
                        story.description = description
                        changed = True
                    for meta_key, col_attr in (
                        ('score',     'literotica_score'),
                        ('views',     'literotica_views'),
                        ('favorites', 'literotica_favorites'),
                        ('comments',  'literotica_comments'),
                    ):
                        val = metadata.get(meta_key)
                        if val is not None and getattr(story, col_attr) is None:
                            setattr(story, col_attr, val)
                            changed = True
                    if changed:
                        db.session.commit()
                        updated += 1
                        log_action(f"[AUTOMATION] Backfilled description for '{story.title}'")
                except Exception as e:
                    db.session.rollback()
                    log_error(f"[AUTOMATION] Failed to backfill description for '{story.title}': {e}")

            if updated:
                log_action(f"[AUTOMATION] Startup description backfill complete: {updated}/{len(stories)} updated")

        except Exception as e:
            log_error(f"[AUTOMATION] Error in startup description backfill: {str(e)}")
