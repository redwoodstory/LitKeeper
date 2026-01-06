from __future__ import annotations
import threading
import time
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
    
    def _run_loop(self):
        time.sleep(30)
        
        while self.running:
            try:
                with self.app.app_context():
                    self._auto_add_stories()
                    self._auto_refresh_metadata()
            except Exception as e:
                log_error(f"[AUTOMATION] Error in background automation: {str(e)}")
            
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
            
            if orphaned_count > 0:
                log_action(f"[AUTOMATION] Found {orphaned_count} new stories in filesystem, adding to library...")
                
                added_count = sync_checker.add_orphaned_files()
                
                if added_count > 0:
                    log_action(f"[AUTOMATION] Successfully added {added_count} stories to library")
                else:
                    log_action(f"[AUTOMATION] No new stories added (duplicates or errors)")
            
        except Exception as e:
            log_error(f"[AUTOMATION] Error auto-adding stories: {str(e)}")
    
    def _auto_refresh_metadata(self):
        try:
            from app.services.metadata_refresh_service import MetadataRefreshService
            
            stories_missing_metadata = Story.query.filter(Story.literotica_url.is_(None)).all()
            
            if not stories_missing_metadata:
                return
            
            log_action(f"[AUTOMATION] Found {len(stories_missing_metadata)} stories missing metadata, checking for auto-matches...")
            
            auto_matched_count = 0
            
            for story in stories_missing_metadata:
                try:
                    service = MetadataRefreshService()
                    
                    search_result = service.search_for_story(story.id)
                    
                    if not search_result.get('success'):
                        continue
                    
                    if not search_result.get('auto_match'):
                        continue
                    
                    best_match = search_result.get('best_match')
                    if not best_match:
                        continue
                    
                    confidence = best_match.get('confidence', 0.0)
                    
                    if confidence >= 1.0:
                        url = best_match['url']
                        log_action(f"[AUTOMATION] Auto-refreshing metadata for '{story.title}' (100% match: {url})")
                        
                        refresh_result = service.refresh_metadata_from_url(story.id, url, method='auto')
                        
                        if refresh_result.get('success'):
                            auto_matched_count += 1
                            fields_changed = refresh_result.get('fields_changed', [])
                            log_action(f"[AUTOMATION] Successfully refreshed metadata for '{story.title}' - Updated: {', '.join(fields_changed)}")
                        else:
                            log_error(f"[AUTOMATION] Failed to refresh metadata for '{story.title}': {refresh_result.get('message')}")
                    
                    time.sleep(2)
                    
                except Exception as e:
                    db.session.rollback()
                    log_error(f"[AUTOMATION] Error processing story '{story.title}': {str(e)}")
                    continue
            
            if auto_matched_count > 0:
                log_action(f"[AUTOMATION] Auto-refreshed metadata for {auto_matched_count} stories with 100% matches")
        
        except Exception as e:
            db.session.rollback()
            log_error(f"[AUTOMATION] Error auto-refreshing metadata: {str(e)}")
