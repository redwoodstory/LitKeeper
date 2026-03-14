from __future__ import annotations
from typing import Optional, Dict, List
from datetime import datetime
import time
import random
import traceback
import hashlib
import glob
import os
import shutil
from flask import Flask
from app.models import Story, StoryFormat, db
from app.services.story_downloader import download_story, extract_chapter_titles
from app.services.logger import log_action, log_error
from app.services.notifier import send_notification
from app.services.epub_generator import create_epub_file
from app.services.html_generator import create_html_file
from app.utils import get_epub_directory, get_html_directory, get_archive_directory

UPDATE_CHECK_DELAY_MIN_SECONDS = 30
UPDATE_CHECK_DELAY_MAX_SECONDS = 60

MIN_CONTENT_CHARS = 500
CHAPTER_DROP_THRESHOLD = 0.20
WORD_DROP_THRESHOLD = 0.30
MAX_ARCHIVED_VERSIONS = 3


class StoryUpdateChecker:

    def __init__(self):
        pass

    def _validate_update_content(self, story: Story, update_info: Dict) -> tuple[bool, str]:
        story_content = update_info['story_content']
        new_chapter_count = update_info['new_chapter_count']

        if len(story_content) < MIN_CONTENT_CHARS:
            return False, f"content too short ({len(story_content)} chars, minimum {MIN_CONTENT_CHARS})"

        if new_chapter_count < 1:
            return False, f"no chapters detected (chapter count: {new_chapter_count})"

        old_chapters = story.chapter_count or 0
        if old_chapters > 0:
            drop_ratio = (old_chapters - new_chapter_count) / old_chapters
            if drop_ratio > CHAPTER_DROP_THRESHOLD:
                return False, (
                    f"chapter count dropped by {drop_ratio:.0%} "
                    f"({old_chapters} -> {new_chapter_count})"
                )

        old_word_count = story.word_count or 0
        if old_word_count > 0:
            new_word_count = len(story_content.split())
            drop_ratio = (old_word_count - new_word_count) / old_word_count
            if drop_ratio > WORD_DROP_THRESHOLD:
                return False, (
                    f"word count dropped by {drop_ratio:.0%} "
                    f"({old_word_count:,} -> {new_word_count:,})"
                )

        return True, ""

    def _archive_story_files(self, old_formats: list, filename_base: str) -> Dict[str, str]:
        archive_dir = get_archive_directory()
        os.makedirs(archive_dir, exist_ok=True)
        date_tag = datetime.utcnow().strftime('%Y%m%d')
        archived: Dict[str, str] = {}
        for fmt in old_formats:
            if fmt.file_path and os.path.exists(fmt.file_path):
                ext = os.path.splitext(fmt.file_path)[1]
                archive_path = os.path.join(archive_dir, f"{filename_base}_{date_tag}{ext}")
                shutil.move(fmt.file_path, archive_path)
                archived[fmt.file_path] = archive_path
                log_action(f"Archived: {os.path.basename(fmt.file_path)} -> {os.path.basename(archive_path)}")
        return archived

    def _restore_from_archive(self, archived: Dict[str, str]) -> None:
        for original_path, archive_path in archived.items():
            if os.path.exists(archive_path):
                try:
                    shutil.move(archive_path, original_path)
                    log_action(f"Restored: {os.path.basename(original_path)}")
                except Exception as e:
                    log_error(f"Failed to restore {original_path} from archive: {e}")

    def _prune_archive(self, filename_base: str) -> None:
        archive_dir = get_archive_directory()
        for ext in ('.epub', '.json'):
            pattern = os.path.join(archive_dir, f"{filename_base}_*{ext}")
            versions = sorted(glob.glob(pattern))
            for old_file in versions[:-MAX_ARCHIVED_VERSIONS]:
                try:
                    os.remove(old_file)
                    log_action(f"Pruned archive: {os.path.basename(old_file)}")
                except Exception as e:
                    log_error(f"Failed to prune archive file {old_file}: {e}")

    def check_for_updates(self, story: Story) -> Optional[Dict]:
        """
        Check if a story has updates available on Literotica.

        Returns:
            Dict with update info if update found, None otherwise
        """
        if not story.literotica_url:
            log_action(f"Skipping update check for '{story.title}': no Literotica URL")
            return None

        try:
            log_action(f"Checking for updates: '{story.title}'")

            story_content, _, _, _, _, _, new_page_count, _, new_description = download_story(story.literotica_url)

            if not story_content:
                log_error(f"Failed to fetch story for update check: '{story.title}'")
                return None

            content_hash = hashlib.sha256(story_content.encode('utf-8')).hexdigest()

            new_chapter_count = story_content.count("\n\nChapter ")

            has_update = False

            if story.content_hash and story.content_hash != content_hash:
                has_update = True

            elif story.literotica_page_count and new_page_count and new_page_count > story.literotica_page_count:
                has_update = True

            elif story.chapter_count and new_chapter_count > story.chapter_count:
                has_update = True

            if not story.content_hash:
                log_action(f"Initializing content hash for '{story.title}'")
                has_update = False

            if not story.description and new_description:
                story.description = new_description

            story.last_update_check_at = datetime.utcnow()

            if not has_update:
                story.content_hash = content_hash
                db.session.commit()
                return None

            return {
                'has_update': True,
                'old_page_count': story.literotica_page_count,
                'new_page_count': new_page_count,
                'old_chapter_count': story.chapter_count,
                'new_chapter_count': new_chapter_count,
                'content_hash': content_hash,
                'story_content': story_content
            }

        except Exception as e:
            log_error(f"Error checking for updates on '{story.title}': {str(e)}\n{traceback.format_exc()}")
            return None

    def check_for_updates_via_series(self, story: Story) -> Optional[Dict]:
        """
        Check for updates using series page (fast path).
        Falls back to full download if series URL not available.
        """
        if not story.literotica_series_url:
            log_action(f"No series URL for '{story.title}', using full download method")
            return self.check_for_updates(story)

        try:
            from app.services.series_page_checker import SeriesPageChecker

            log_action(f"Quick-checking series for '{story.title}'")
            checker = SeriesPageChecker()
            series_info = checker.check_series_parts(story.literotica_series_url)

            if not series_info:
                log_action(f"Series page check failed for '{story.title}', falling back")
                return self.check_for_updates(story)

            new_part_count = series_info['total_parts']

            if story.chapter_count and new_part_count > story.chapter_count:
                log_action(f"Update detected: {story.chapter_count} -> {new_part_count} parts")
                return self.check_for_updates(story)

            story.last_update_check_at = datetime.utcnow()
            db.session.commit()
            log_action(f"No updates for '{story.title}'")
            return None

        except Exception as e:
            log_error(f"Error in series-based update check: {str(e)}")
            return self.check_for_updates(story)

    def update_story(self, story: Story, update_info: Dict) -> bool:
        """
        Update a story with new content, preserving reading progress.

        Returns:
            True if update successful, False otherwise
        """
        try:
            is_valid, rejection_reason = self._validate_update_content(story, update_info)
            if not is_valid:
                old_chapters = story.chapter_count or 0
                new_chapters = update_info['new_chapter_count']
                old_words = story.word_count or 0
                new_words = len(update_info['story_content'].split())
                send_notification(
                    f'Auto-update SKIPPED for "{story.title}": {rejection_reason}.\n'
                    f'Chapters: {old_chapters} stored / {new_chapters} downloaded\n'
                    f'Words: {old_words:,} stored / {new_words:,} downloaded\n'
                    f'URL: {story.literotica_url}',
                    is_error=True
                )
                log_error(f"Content validation rejected update for '{story.title}': {rejection_reason}")
                return False

            log_action(f"Updating story: '{story.title}'")

            reading_progress = story.reading_progress
            progress_data = None
            if reading_progress:
                progress_data = {
                    'current_chapter': reading_progress.current_chapter,
                    'current_paragraph': reading_progress.current_paragraph,
                    'scroll_position': reading_progress.scroll_position,
                    'cfi': reading_progress.cfi,
                    'is_completed': reading_progress.is_completed,
                    'reading_duration_seconds': reading_progress.reading_duration_seconds,
                    'last_read_at': reading_progress.last_read_at
                }

            old_formats = list(story.formats)
            epub_dir = get_epub_directory()
            html_dir = get_html_directory()

            archived = self._archive_story_files(old_formats, story.filename_base)

            for story_format in old_formats:
                db.session.delete(story_format)

            story_content = update_info['story_content']
            chapter_titles = extract_chapter_titles(story_content)

            try:
                epub_path = create_epub_file(
                    story_title=story.title,
                    story_author=story.author.name,
                    story_content=story_content,
                    output_directory=epub_dir,
                    story_category=story.category.name if story.category else None,
                    story_tags=[tag.name for tag in story.tags]
                )

                epub_format = StoryFormat(
                    story_id=story.id,
                    format_type='epub',
                    file_path=epub_path,
                    file_size=os.path.getsize(epub_path)
                )
                db.session.add(epub_format)

                json_path = create_html_file(
                    story_title=story.title,
                    story_author=story.author.name,
                    story_content=story_content,
                    output_directory=html_dir,
                    story_category=story.category.name if story.category else None,
                    story_tags=[tag.name for tag in story.tags],
                    chapter_titles=chapter_titles if chapter_titles else None,
                    source_url=story.literotica_url,
                    author_url=story.author.literotica_url if story.author else None,
                    page_count=update_info['new_page_count']
                )

                import json
                with open(json_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)

                json_format = StoryFormat(
                    story_id=story.id,
                    format_type='json',
                    file_path=json_path,
                    file_size=os.path.getsize(json_path),
                    json_data=json.dumps(json_data)
                )
                db.session.add(json_format)

                story.literotica_page_count = update_info['new_page_count']
                story.chapter_count = update_info['new_chapter_count']
                story.content_hash = update_info['content_hash']
                story.last_metadata_refresh = datetime.utcnow()

                db.session.commit()

                self._prune_archive(story.filename_base)

            except Exception as gen_error:
                log_error(f"Generation failed for '{story.title}': {str(gen_error)}\n{traceback.format_exc()}")
                self._restore_from_archive(archived)
                db.session.rollback()
                return False

            if progress_data and not story.reading_progress:
                from app.models.reader import ReadingProgress
                new_progress = ReadingProgress(
                    story_id=story.id,
                    **progress_data
                )
                db.session.add(new_progress)
                db.session.commit()

            log_action(f"Successfully updated story: '{story.title}'")
            return True

        except Exception as e:
            db.session.rollback()
            log_error(f"Failed to update story '{story.title}': {str(e)}\n{traceback.format_exc()}")
            return False


def check_all_stories_for_updates(app: Flask) -> None:
    """
    Check all enabled stories for updates.
    Runs in scheduler context with Flask app context.
    """
    with app.app_context():
        try:
            log_action("Starting scheduled story update check")

            stories = Story.query.filter(
                Story.auto_update_enabled == True,
                Story.literotica_url.isnot(None)
            ).all()

            if not stories:
                log_action("No stories configured for auto-updates")
                return

            log_action(f"Checking {len(stories)} stories for updates")

            checker = StoryUpdateChecker()
            updates_found = []

            for i, story in enumerate(stories):
                if i > 0:
                    delay = random.randint(UPDATE_CHECK_DELAY_MIN_SECONDS, UPDATE_CHECK_DELAY_MAX_SECONDS)
                    log_action(f"Waiting {delay} seconds before next check (rate limiting)...")
                    time.sleep(delay)

                update_info = checker.check_for_updates_via_series(story)

                if update_info and update_info.get('has_update'):
                    log_action(f"Update found for '{story.title}': {update_info['old_chapter_count']} -> {update_info['new_chapter_count']} chapters")

                    if checker.update_story(story, update_info):
                        updates_found.append({
                            'title': story.title,
                            'old_chapters': update_info['old_chapter_count'],
                            'new_chapters': update_info['new_chapter_count']
                        })

            if updates_found:
                summary_lines = [f"- {u['title']}: {u['old_chapters']} -> {u['new_chapters']} chapters" for u in updates_found]
                summary = "\n".join(summary_lines)
                send_notification(f"Story updates found ({len(updates_found)}):\n{summary}")
                log_action(f"Update check complete: {len(updates_found)} stories updated")
            else:
                log_action("Update check complete: no updates found")

        except Exception as e:
            log_error(f"Error in scheduled update check: {str(e)}\n{traceback.format_exc()}")
            send_notification(f"Story update check failed: {str(e)}", is_error=True)
