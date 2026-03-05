from __future__ import annotations
import threading
import time
import random
from datetime import datetime
from typing import Optional
from app.services.logger import log_action, log_error
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
                    self._auto_add_stories()
                    self._auto_refresh_metadata()

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
        
        while self.running:
            try:
                self.is_processing = True
                self.last_run_time = datetime.utcnow()
                
                with self.app.app_context():
                    self._auto_add_stories()
                    self._auto_refresh_metadata()
                
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
