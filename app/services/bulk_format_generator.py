from __future__ import annotations
import json
import os
from typing import Optional
from datetime import datetime
from app.models import Story, StoryFormat, db
from app.services.format_generator import FormatGeneratorService
from app.services.metadata_refresh_service import MetadataRefreshService
from app.services.cover_generator import generate_cover_image
from app.services.epub_service import EpubService
from app.services.logger import log_action, log_error
from app.utils import get_data_directory, get_cover_directory, get_epub_directory
from sqlalchemy.orm import joinedload


class BulkFormatGeneratorService:
    def __init__(self):
        self.format_service = FormatGeneratorService()
        self.metadata_service = MetadataRefreshService()
        self.log_file = os.path.join(get_data_directory(), 'logs', 'bulk_generation.log')
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
    
    def _write_log(self, message: str, level: str = "info"):
        timestamp = datetime.utcnow().isoformat()
        log_entry = f"[{timestamp}] [{level.upper()}] {message}\n"
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        
        if level == "error":
            log_error(message)
        else:
            log_action(message)
    
    def _find_100_percent_match(self, story: Story) -> Optional[str]:
        if story.literotica_url:
            return story.literotica_url
        
        search_result = self.metadata_service.search_for_story(story.id)
        
        if not search_result.get('success'):
            return None
        
        if not search_result.get('auto_match'):
            return None
        
        best_match = search_result.get('best_match')
        if not best_match:
            return None
        
        confidence = best_match.get('confidence', 0.0)
        if confidence >= 1.0:
            return best_match.get('url')
        
        return None
    
    def generate_missing_epubs(self) -> dict:
        self._write_log("Starting bulk EPUB generation")
        
        stories_without_epub = Story.query.filter(
            ~Story.formats.any(StoryFormat.format_type == 'epub'),
            Story.formats.any(StoryFormat.format_type == 'json')
        ).all()
        
        total = len(stories_without_epub)
        successful = 0
        failed = 0
        errors = []
        
        self._write_log(f"Found {total} stories without EPUB format")
        
        for story in stories_without_epub:
            try:
                self._write_log(f"Generating EPUB for: {story.title} by {story.author.name}")
                result = self.format_service.generate_epub_from_json(story.id)
                
                if result.get('success'):
                    successful += 1
                    self._write_log(f"✓ Successfully generated EPUB for: {story.title}")
                else:
                    failed += 1
                    error_msg = f"✗ Failed to generate EPUB for: {story.title} - {result.get('message')}"
                    self._write_log(error_msg, "error")
                    errors.append({
                        "story_id": story.id,
                        "title": story.title,
                        "error": result.get('message')
                    })
            except Exception as e:
                failed += 1
                error_msg = f"✗ Exception generating EPUB for: {story.title} - {str(e)}"
                self._write_log(error_msg, "error")
                errors.append({
                    "story_id": story.id,
                    "title": story.title,
                    "error": str(e)
                })
        
        summary = f"EPUB generation complete: {successful} successful, {failed} failed out of {total} total"
        self._write_log(summary)
        
        return {
            "success": True,
            "total": total,
            "successful": successful,
            "failed": failed,
            "errors": errors,
            "message": summary
        }
    
    def generate_missing_html(self) -> dict:
        self._write_log("Starting bulk HTML generation")
        
        stories_without_html = Story.query.filter(
            Story.formats.any(StoryFormat.format_type == 'epub'),
            ~Story.formats.any(StoryFormat.format_type == 'json')
        ).all()
        
        total = len(stories_without_html)
        successful = 0
        failed = 0
        skipped = 0
        errors = []
        no_match_stories = []
        
        self._write_log(f"Found {total} stories without HTML format")
        
        for story in stories_without_html:
            try:
                self._write_log(f"Processing: {story.title} by {story.author.name}")
                
                url = self._find_100_percent_match(story)
                
                if not url:
                    skipped += 1
                    msg = f"⊘ Skipped: {story.title} - No 100% match found"
                    self._write_log(msg, "info")
                    no_match_stories.append({
                        "story_id": story.id,
                        "title": story.title,
                        "author": story.author.name
                    })
                    continue
                
                self._write_log(f"Found 100% match for: {story.title} at {url}")
                result = self.format_service.generate_html_with_metadata(
                    story.id, 
                    url, 
                    method="auto"
                )
                
                if result.get('success'):
                    successful += 1
                    self._write_log(f"✓ Successfully generated HTML for: {story.title}")
                else:
                    failed += 1
                    error_msg = f"✗ Failed to generate HTML for: {story.title} - {result.get('message')}"
                    self._write_log(error_msg, "error")
                    errors.append({
                        "story_id": story.id,
                        "title": story.title,
                        "error": result.get('message')
                    })
            except Exception as e:
                failed += 1
                error_msg = f"✗ Exception generating HTML for: {story.title} - {str(e)}"
                self._write_log(error_msg, "error")
                errors.append({
                    "story_id": story.id,
                    "title": story.title,
                    "error": str(e)
                })
        
        summary = f"HTML generation complete: {successful} successful, {failed} failed, {skipped} skipped (no match) out of {total} total"
        self._write_log(summary)
        
        return {
            "success": True,
            "total": total,
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "no_match_stories": no_match_stories,
            "message": summary
        }
    
    def generate_all_missing_formats(self) -> dict:
        self._write_log("Starting generation of all missing formats")
        
        epub_result = self.generate_missing_epubs()
        html_result = self.generate_missing_html()
        
        total_successful = epub_result['successful'] + html_result['successful']
        total_failed = epub_result['failed'] + html_result['failed']
        total_skipped = html_result.get('skipped', 0)
        total_processed = epub_result['total'] + html_result['total']
        
        summary = f"All formats generation complete: {total_successful} successful, {total_failed} failed, {total_skipped} skipped out of {total_processed} total operations"
        self._write_log(summary)
        
        return {
            "success": True,
            "epub_result": epub_result,
            "html_result": html_result,
            "total_successful": total_successful,
            "total_failed": total_failed,
            "total_skipped": total_skipped,
            "message": summary
        }
    
    def regenerate_all_covers(self) -> dict:
        self._write_log("Starting bulk cover regeneration")
        stories = Story.query.options(joinedload(Story.author), joinedload(Story.formats)).all()
        total = len(stories)
        successful = 0
        failed = 0
        errors: list[dict] = []
        cover_dir = get_cover_directory()
        epub_dir = get_epub_directory()
        os.makedirs(cover_dir, exist_ok=True)

        self._write_log(f"Found {total} stories to regenerate covers for")

        for story in stories:
            try:
                author_name = story.author.name if story.author else 'Unknown Author'
                cover_filename = f"{story.id}_{story.filename_base}.jpg"
                cover_path = os.path.join(cover_dir, cover_filename)

                category_name = story.category.name if story.category else None
                generate_cover_image(story.title, author_name, cover_path, category=category_name)

                epub_fmt = next((f for f in story.formats if f.format_type == 'epub'), None)
                if epub_fmt and os.path.exists(epub_fmt.file_path):
                    EpubService.update_epub_cover(epub_fmt.file_path, cover_path)

                story.cover_filename = cover_filename
                db.session.commit()

                successful += 1
                self._write_log(f"✓ Regenerated cover for: {story.title}")
            except Exception as e:
                failed += 1
                error_msg = f"✗ Failed cover for: {story.title} - {str(e)}"
                self._write_log(error_msg, "error")
                errors.append({"story_id": story.id, "title": story.title, "error": str(e)})

        summary = f"Cover regeneration complete: {successful} successful, {failed} failed out of {total} total"
        self._write_log(summary)
        return {
            "success": True,
            "total": total,
            "successful": successful,
            "failed": failed,
            "errors": errors,
            "message": summary,
        }

    def reembed_existing_covers(self) -> dict:
        self._write_log("Starting cover re-embed into EPUBs")
        stories = Story.query.options(joinedload(Story.author), joinedload(Story.formats)).all()
        epub_stories = [s for s in stories if any(f.format_type == 'epub' for f in s.formats)]
        total = len(epub_stories)
        successful = 0
        failed = 0
        errors: list[dict] = []
        cover_dir = get_cover_directory()
        epub_dir = get_epub_directory()

        self._write_log(f"Found {total} EPUBs to update with existing covers")

        for story in epub_stories:
            try:
                cover_filename = f"{story.id}_{story.filename_base}.jpg"
                cover_path = os.path.join(cover_dir, cover_filename)
                epub_fmt = next((f for f in story.formats if f.format_type == 'epub'), None)
                epub_path = epub_fmt.file_path if epub_fmt else None

                if not epub_path or not os.path.exists(cover_path) or not os.path.exists(epub_path):
                    total -= 1
                    continue

                EpubService.update_epub_cover(epub_path, cover_path)
                successful += 1
                self._write_log(f"✓ Re-embedded cover for: {story.title}")
            except Exception as e:
                failed += 1
                error_msg = f"✗ Failed re-embed for: {story.title} - {str(e)}"
                self._write_log(error_msg, "error")
                errors.append({"story_id": story.id, "title": story.title, "error": str(e)})

        summary = f"Cover re-embed complete: {successful} successful, {failed} failed out of {total} EPUBs"
        self._write_log(summary)
        return {
            "success": True,
            "total": total,
            "successful": successful,
            "failed": failed,
            "errors": errors,
            "message": summary,
        }

    def repair_all_epub_metadata(self) -> dict:
        self._write_log("Starting bulk EPUB metadata repair")
        epub_dir = get_epub_directory()
        epub_files = [f for f in os.listdir(epub_dir) if f.endswith('.epub')] if os.path.isdir(epub_dir) else []
        total = len(epub_files)
        repaired = 0
        skipped = 0
        errors: list[dict] = []

        self._write_log(f"Found {total} EPUB files to inspect")

        for filename in epub_files:
            epub_path = os.path.join(epub_dir, filename)
            try:
                modified = EpubService.repair_metadata_chapter(epub_path)
                if modified:
                    repaired += 1
                    self._write_log(f"✓ Repaired: {filename}")
                    # Touch story.updated_at so the iOS sync detects the change
                    fmt = StoryFormat.query.filter_by(file_path=epub_path, format_type='epub').first()
                    story = fmt.story if fmt else None
                    if story:
                        story.updated_at = datetime.utcnow()
                        db.session.commit()
                else:
                    skipped += 1
            except Exception as e:
                error_msg = f"✗ Error repairing {filename}: {str(e)}"
                self._write_log(error_msg, "error")
                errors.append({"filename": filename, "error": str(e)})

        summary = f"EPUB metadata repair complete: {repaired} repaired, {skipped} skipped, {len(errors)} errors out of {total} total"
        self._write_log(summary)
        return {
            "success": True,
            "total": total,
            "repaired": repaired,
            "skipped": skipped,
            "errors": errors,
            "message": summary,
        }

    def get_generation_log(self) -> dict:
        if not os.path.exists(self.log_file):
            return {
                "success": True,
                "log_exists": False,
                "entries": []
            }
        
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            entries = []
            for line in lines[-100:]:
                line = line.strip()
                if line:
                    entries.append(line)
            
            return {
                "success": True,
                "log_exists": True,
                "entries": entries
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error reading log: {str(e)}"
            }
