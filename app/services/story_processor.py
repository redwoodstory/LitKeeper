from __future__ import annotations
from typing import Optional
import traceback
import os
import shutil
import glob
from datetime import datetime
from app.utils import get_epub_directory, get_html_directory, get_archive_directory, sanitize_filename
from .story_downloader import download_story, extract_chapter_titles, split_story_chapters
from .epub_generator import create_epub_file
from .html_generator import create_html_file
from .file_operations import copy_to_external_path
from .logger import log_action, log_error
from .notifier import send_notification

_story_cache: dict[str, tuple] = {}


def _get_or_create_story(
    story_title: str,
    story_author: str,
    story_category: Optional[str],
    story_tags: Optional[list[str]],
    source_url: str,
    author_url: Optional[str],
    page_count: Optional[int],
    series_url: Optional[str],
    chapter_count: int,
    word_count: Optional[int],
    story_description: Optional[str],
):
    """
    Locate the existing story record or create a new one.
    Updates mutable metadata fields (word_count, chapter_count, description, etc.) on re-download
    so that the iOS library always reflects current content without creating duplicate records.
    Returns the Story ORM object (with a valid .id after flush), or None if library is disabled.
    """
    enable_library = os.getenv('ENABLE_LIBRARY', 'true').lower() == 'true'
    if not enable_library:
        log_action(f"Skipping database save (ENABLE_LIBRARY=false): '{story_title}'")
        return None

    from app.models import Story, Author, Category, Tag
    from app.models.base import db
    from app.services.migration.deduplicator import Deduplicator

    deduplicator = Deduplicator()
    filename_base = sanitize_filename(story_title)

    duplicate = deduplicator.check_duplicate(
        {'title': story_title, 'author': story_author, 'source_url': source_url},
        filename_base
    )

    if duplicate:
        log_action(f"Story already exists (ID: {duplicate.id}), updating metadata")
        duplicate.word_count = word_count
        duplicate.chapter_count = chapter_count
        duplicate.literotica_page_count = page_count
        if story_description:
            duplicate.description = story_description
        if series_url:
            duplicate.literotica_series_url = series_url
        db.session.flush()
        return duplicate

    author_obj = Author.query.filter_by(name=story_author).first()
    if not author_obj:
        author_obj = Author(name=story_author, literotica_url=author_url)
        db.session.add(author_obj)
        db.session.flush()

    category_obj = None
    if story_category:
        category_obj = Category.query.filter_by(name=story_category).first()
        if not category_obj:
            category_obj = Category(
                name=story_category,
                slug=Category.create_slug(story_category)
            )
            db.session.add(category_obj)
            db.session.flush()

    story = Story(
        title=story_title,
        author_id=author_obj.id,
        category_id=category_obj.id if category_obj else None,
        literotica_url=source_url,
        literotica_series_url=series_url,
        literotica_page_count=page_count,
        chapter_count=chapter_count,
        word_count=word_count,
        filename_base=filename_base,
        imported_at=datetime.utcnow(),
        metadata_refresh_status='complete' if source_url else 'never',
        description=story_description
    )
    db.session.add(story)
    db.session.flush()  # assign story.id before we name the files

    if story_tags:
        tag_objects = []
        seen_slugs = set()
        for tag_name in story_tags:
            tag_slug = Tag.create_slug(tag_name)
            if tag_slug in seen_slugs:
                continue
            seen_slugs.add(tag_slug)
            tag = Tag.query.filter_by(slug=tag_slug).first()
            if not tag:
                tag = Tag(name=tag_name, slug=tag_slug)
                db.session.add(tag)
                db.session.flush()
            tag_objects.append(tag)
        story.tags = tag_objects

    return story


def _link_story_formats(story) -> None:
    """
    Create or update StoryFormat records for files on disk.
    Files are expected at "{story.id}_{story.filename_base}.epub/.json".
    If an existing format record points to a different path, it is updated to the new one.
    """
    import json as _json
    from app.models import StoryFormat
    from app.models.base import db

    file_base = f"{story.id}_{story.filename_base}"

    epub_path = os.path.join(get_epub_directory(), f"{file_base}.epub")
    existing_epub = StoryFormat.query.filter_by(story_id=story.id, format_type='epub').first()
    if os.path.exists(epub_path):
        if not existing_epub:
            db.session.add(StoryFormat(
                story_id=story.id,
                format_type='epub',
                file_path=epub_path,
                file_size=os.path.getsize(epub_path)
            ))
            log_action(f"Added EPUB format record for story ID {story.id}")
        elif existing_epub.file_path != epub_path:
            existing_epub.file_path = epub_path
            existing_epub.file_size = os.path.getsize(epub_path)
            log_action(f"Updated EPUB path for story ID {story.id}")

    json_path = os.path.join(get_html_directory(), f"{file_base}.json")
    existing_json = StoryFormat.query.filter_by(story_id=story.id, format_type='json').first()
    if os.path.exists(json_path):
        if not existing_json:
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = _json.load(f)
            db.session.add(StoryFormat(
                story_id=story.id,
                format_type='json',
                file_path=json_path,
                file_size=os.path.getsize(json_path),
                json_data=_json.dumps(json_data)
            ))
            log_action(f"Added JSON format record for story ID {story.id}")
        elif existing_json.file_path != json_path:
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = _json.load(f)
            existing_json.file_path = json_path
            existing_json.file_size = os.path.getsize(json_path)
            existing_json.json_data = _json.dumps(json_data)
            log_action(f"Updated JSON path for story ID {story.id}")

    db.session.commit()
    log_action(f"Saved story to database: '{story.title}' (ID: {story.id})")


def _create_story_files(
    story_content: str,
    story_title: str,
    story_author: str,
    story_category: Optional[str],
    story_tags: Optional[list[str]],
    source_url: str,
    author_url: Optional[str],
    page_count: Optional[int],
    formats: list[str],
    series_url: Optional[str] = None,
    story_description: Optional[str] = None
) -> dict:
    """
    Get/create the story DB record first (to obtain a stable ID), then write files
    named "{story.id}_{story.filename_base}.epub/.json" so each file is unambiguously
    tied to its database record regardless of title changes.
    """
    try:
        chapter_count = max(len(split_story_chapters(story_content)) - 1, 1) if story_content else 1
        word_count = len(story_content.split()) if story_content else 0

        # 1. DB first — get or create story record to obtain a stable story.id.
        story = None
        try:
            story = _get_or_create_story(
                story_title=story_title,
                story_author=story_author,
                story_category=story_category,
                story_tags=story_tags,
                source_url=source_url,
                author_url=author_url,
                page_count=page_count,
                series_url=series_url,
                chapter_count=chapter_count,
                word_count=word_count,
                story_description=story_description,
            )
        except Exception as e:
            try:
                from app.models.base import db
                db.session.rollback()
            except Exception:
                pass
            log_error(f"Failed to get/create story record: {str(e)}\n{traceback.format_exc()}")

        # 2. Archive existing files before overwriting (only for existing stories being re-downloaded).
        if story is not None and story.formats:
            archive_dir = get_archive_directory()
            os.makedirs(archive_dir, exist_ok=True)
            date_tag = datetime.utcnow().strftime('%Y%m%d')
            for fmt in list(story.formats):
                if fmt.file_path and os.path.exists(fmt.file_path):
                    ext = os.path.splitext(fmt.file_path)[1]
                    archive_path = os.path.join(archive_dir, f"{story.filename_base}_{date_tag}{ext}")
                    shutil.move(fmt.file_path, archive_path)
                    log_action(f"Archived: {os.path.basename(fmt.file_path)} -> {os.path.basename(archive_path)}")
            # Prune to keep at most 3 archived versions per story.
            for ext in ('.epub', '.json'):
                pattern = os.path.join(archive_dir, f"{story.filename_base}_*{ext}")
                versions = sorted(glob.glob(pattern))
                for old_file in versions[:-3]:
                    try:
                        os.remove(old_file)
                        log_action(f"Pruned archive: {os.path.basename(old_file)}")
                    except Exception as prune_err:
                        log_error(f"Failed to prune archive file {old_file}: {prune_err}")

        # 3. Derive file base: use "{story.id}_{story.filename_base}" when we have a DB record
        #    so files are permanently tied to their story ID.
        if story is not None:
            file_base = f"{story.id}_{story.filename_base}"
        else:
            file_base = sanitize_filename(story_title)

        # 4. Write files to disk.
        created_files = []

        if "epub" in formats:
            epub_file_name = create_epub_file(
                story_title,
                story_author,
                story_content,
                get_epub_directory(),
                story_category=story_category,
                story_tags=story_tags,
                story_description=story_description,
                filename_base=file_base,
            )
            created_files.append(f"EPUB: {epub_file_name.split('/')[-1]}")
            log_action(f"Created EPUB: {epub_file_name}")

            external_epub = copy_to_external_path(epub_file_name, 'epub')
            if external_epub:
                log_action(f"Copied EPUB to external path: {external_epub}")

        if "html" in formats:
            chapter_titles = extract_chapter_titles(story_content)
            html_file_name = create_html_file(
                story_title,
                story_author,
                story_content,
                get_html_directory(),
                story_category=story_category,
                story_tags=story_tags,
                chapter_titles=chapter_titles if chapter_titles else None,
                source_url=source_url,
                author_url=author_url,
                page_count=page_count,
                filename_base=file_base,
                story_description=story_description,
            )
            created_files.append(f"HTML: {html_file_name.split('/')[-1]}")
            log_action(f"Created HTML: {html_file_name}")

        # 5. Link file paths to StoryFormat records.
        if story is not None:
            try:
                _link_story_formats(story)
            except Exception as e:
                try:
                    from app.models.base import db
                    db.session.rollback()
                except Exception:
                    pass
                log_error(f"Failed to link story formats: {str(e)}\n{traceback.format_exc()}")

        formats_str = " and ".join(created_files)
        return {
            'success': True,
            'message': f"Successfully saved '{story_title}' by {story_author}",
            'files': created_files,
            'formats_str': formats_str
        }

    except Exception as e:
        error_msg = f"Failed to create story files: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg, source_url)
        return {
            'success': False,
            'message': str(e),
            'error': error_msg
        }


class StoryProcessingResult:
    def __init__(
        self,
        success: bool,
        message: str,
        title: Optional[str] = None,
        author: Optional[str] = None,
        formats: Optional[list[str]] = None,
        files: Optional[list[str]] = None,
        error: Optional[str] = None
    ):
        self.success = success
        self.message = message
        self.title = title
        self.author = author
        self.formats = formats or []
        self.files = files or []
        self.error = error

    def to_dict(self) -> dict:
        result = {
            "success": "true" if self.success else "false",
            "message": self.message
        }
        if self.title:
            result["title"] = self.title
        if self.author:
            result["author"] = self.author
        if self.formats:
            result["formats"] = self.formats
        if self.files:
            result["files"] = self.files
        return result


def save_story_with_metadata(
    url: str,
    formats: list[str],
    title: str,
    author: str,
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
    send_notifications: bool = True
) -> StoryProcessingResult:
    global _story_cache

    try:
        log_action(f"Saving story with custom metadata: '{title}' by {author}")

        if url in _story_cache:
            story_content, _, _, _, _, story_author_url, story_pages, series_url, _ = _story_cache[url]
            del _story_cache[url]
        else:
            story_content, _, _, _, _, story_author_url, story_pages, series_url, _ = download_story(url)

        if not story_content:
            error_msg = f"Failed to retrieve story content from: {url}"
            log_error(error_msg, url)
            if send_notifications:
                send_notification(f"Story save failed: {url}", is_error=True)
            return StoryProcessingResult(
                success=False,
                message=error_msg,
                error=error_msg
            )

        result = _create_story_files(
            story_content=story_content,
            story_title=title,
            story_author=author,
            story_category=category,
            story_tags=tags,
            source_url=url,
            author_url=story_author_url,
            page_count=story_pages,
            formats=formats,
            series_url=series_url
        )

        if not result['success']:
            if send_notifications:
                send_notification(f"Story save failed: {result['message']}", is_error=True)
            return StoryProcessingResult(
                success=False,
                message=result['message'],
                error=result.get('error')
            )

        if send_notifications:
            send_notification(f"Story saved: '{title}' ({result['formats_str']})")

        return StoryProcessingResult(
            success=True,
            message=result['message'],
            title=title,
            author=author,
            formats=formats,
            files=result['files']
        )

    except Exception as e:
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        log_error(error_msg, url)
        if send_notifications:
            send_notification(f"Error saving story: {str(e)}", is_error=True)
        return StoryProcessingResult(
            success=False,
            message=str(e),
            error=error_msg
        )

def download_story_and_create_files(
    url: str,
    formats: Optional[list[str]] = None,
    send_notifications: bool = True
) -> StoryProcessingResult:
    if formats is None:
        formats = ["epub"]

    try:
        log_action(f"Starting download: {url}")
        story_content, story_title, story_author, story_category, story_tags, story_author_url, story_pages, series_url, story_description = download_story(url)

        if not story_content:
            error_msg = f"Failed to download story from: {url}"
            log_error(error_msg, url)
            if send_notifications:
                send_notification(f"Story download failed: {url}", is_error=True)
            return StoryProcessingResult(
                success=False,
                message=error_msg,
                error=error_msg
            )

        log_action(f"Downloaded: '{story_title}' by {story_author}")

        result = _create_story_files(
            story_content=story_content,
            story_title=story_title,
            story_author=story_author,
            story_category=story_category,
            story_tags=story_tags,
            source_url=url,
            author_url=story_author_url,
            page_count=story_pages,
            formats=formats,
            series_url=series_url,
            story_description=story_description
        )

        if not result['success']:
            if send_notifications:
                send_notification(f"Story save failed: {result['message']}", is_error=True)
            return StoryProcessingResult(
                success=False,
                message=result['message'],
                error=result.get('error')
            )

        if send_notifications:
            send_notification(f"Story downloaded: '{story_title}' ({result['formats_str']})")

        return StoryProcessingResult(
            success=True,
            message=result['message'],
            title=story_title,
            author=story_author,
            formats=formats,
            files=result['files']
        )

    except Exception as e:
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        log_error(error_msg, url)
        if send_notifications:
            send_notification(f"Error processing story: {str(e)}", is_error=True)
        return StoryProcessingResult(
            success=False,
            message=str(e),
            error=error_msg
        )
