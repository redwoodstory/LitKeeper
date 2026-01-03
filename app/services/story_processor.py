from __future__ import annotations
from typing import Optional
import traceback
import os
from datetime import datetime
from app.utils import get_epub_directory, get_html_directory
from .story_downloader import download_story, extract_chapter_titles
from .epub_generator import create_epub_file
from .html_generator import create_html_file
from .file_operations import copy_to_secondary_output
from .logger import log_action, log_error
from .notifier import send_notification

_story_cache: dict[str, tuple] = {}


def _save_to_database(
    story_title: str,
    story_author: str,
    story_category: Optional[str],
    story_tags: Optional[list[str]],
    source_url: str,
    author_url: Optional[str],
    page_count: Optional[int],
    formats: list[str]
) -> None:
    """
    Save story metadata to database only if ENABLE_LIBRARY is true.
    """
    enable_library = os.getenv('ENABLE_LIBRARY', 'true').lower() == 'true'
    if not enable_library:
        log_action(f"Skipping database save (ENABLE_LIBRARY=false): '{story_title}'")
        return
    
    try:
        from app.models import Story, Author, Category, Tag, StoryFormat
        from app.models.base import db
        from app.services.migration.deduplicator import Deduplicator

        deduplicator = Deduplicator()

        filename_base = story_title.replace('/', '_').replace('\\', '_')

        duplicate = deduplicator.check_duplicate(
            {'title': story_title, 'author': story_author, 'source_url': source_url},
            filename_base
        )

        if duplicate:
            log_action(f"Story already exists in database (ID: {duplicate.id}), skipping database save")
            return

        author_obj = Author.query.filter_by(name=story_author).first()
        if not author_obj:
            author_obj = Author(
                name=story_author,
                literotica_url=author_url
            )
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
            literotica_page_count=page_count,
            chapter_count=1,
            filename_base=filename_base,
            imported_at=datetime.utcnow(),
            metadata_refresh_status='complete' if source_url else 'never'
        )
        db.session.add(story)
        db.session.flush()

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

        epub_directory = get_epub_directory()
        html_directory = get_html_directory()

        epub_path = os.path.join(epub_directory, f"{filename_base}.epub")
        if os.path.exists(epub_path):
            story_format = StoryFormat(
                story_id=story.id,
                format_type='epub',
                file_path=epub_path,
                file_size=os.path.getsize(epub_path)
            )
            db.session.add(story_format)

        json_path = os.path.join(html_directory, f"{filename_base}.json")
        if os.path.exists(json_path):
            import json
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)

            story_format = StoryFormat(
                story_id=story.id,
                format_type='json',
                file_path=json_path,
                file_size=os.path.getsize(json_path),
                json_data=json.dumps(json_data)
            )
            db.session.add(story_format)

        db.session.commit()
        log_action(f"Saved story metadata to database: '{story_title}' (ID: {story.id})")

    except Exception as e:
        try:
            from app.models.base import db
            db.session.rollback()
        except:
            pass
        log_error(f"Failed to save story to database: {str(e)}\n{traceback.format_exc()}")


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
            story_content, _, _, _, _, story_author_url, story_pages = _story_cache[url]
            del _story_cache[url]
        else:
            story_content, _, _, _, _, story_author_url, story_pages = download_story(url)

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

        created_files = []

        if "epub" in formats:
            epub_file_name = create_epub_file(
                title,
                author,
                story_content,
                get_epub_directory(),
                story_category=category,
                story_tags=tags
            )
            created_files.append(f"EPUB: {epub_file_name.split('/')[-1]}")
            log_action(f"Created EPUB: {epub_file_name}")

            secondary_epub = copy_to_secondary_output(epub_file_name, 'epub')
            if secondary_epub:
                log_action(f"Copied EPUB to secondary output: {secondary_epub}")

        if "html" in formats:
            chapter_titles = extract_chapter_titles(story_content)

            html_file_name = create_html_file(
                title,
                author,
                story_content,
                get_html_directory(),
                story_category=category,
                story_tags=tags,
                chapter_titles=chapter_titles if chapter_titles else None,
                source_url=url,
                author_url=story_author_url,
                page_count=story_pages
            )
            created_files.append(f"HTML: {html_file_name.split('/')[-1]}")
            log_action(f"Created HTML: {html_file_name}")

        formats_str = " and ".join(created_files)
        success_msg = f"Successfully saved '{title}' by {author}"

        _save_to_database(
            story_title=title,
            story_author=author,
            story_category=category,
            story_tags=tags,
            source_url=url,
            author_url=story_author_url,
            page_count=story_pages,
            formats=formats
        )

        if send_notifications:
            send_notification(f"Story saved: '{title}' ({formats_str})")

        return StoryProcessingResult(
            success=True,
            message=success_msg,
            title=title,
            author=author,
            formats=formats,
            files=created_files
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
        story_content, story_title, story_author, story_category, story_tags, story_author_url, story_pages = download_story(url)

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
        created_files = []

        if "epub" in formats:
            epub_file_name = create_epub_file(
                story_title,
                story_author,
                story_content,
                get_epub_directory(),
                story_category=story_category,
                story_tags=story_tags
            )
            created_files.append(f"EPUB: {epub_file_name.split('/')[-1]}")
            log_action(f"Created EPUB: {epub_file_name}")

            secondary_epub = copy_to_secondary_output(epub_file_name, 'epub')
            if secondary_epub:
                log_action(f"Copied EPUB to secondary output: {secondary_epub}")

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
                source_url=url,
                author_url=story_author_url,
                page_count=story_pages
            )
            created_files.append(f"HTML: {html_file_name.split('/')[-1]}")
            log_action(f"Created HTML: {html_file_name}")

        formats_str = " and ".join(created_files)
        success_msg = f"Successfully downloaded '{story_title}' by {story_author}"

        _save_to_database(
            story_title=story_title,
            story_author=story_author,
            story_category=story_category,
            story_tags=story_tags,
            source_url=url,
            author_url=story_author_url,
            page_count=story_pages,
            formats=formats
        )

        if send_notifications:
            send_notification(f"Story downloaded: '{story_title}' ({formats_str})")

        return StoryProcessingResult(
            success=True,
            message=success_msg,
            title=story_title,
            author=story_author,
            formats=formats,
            files=created_files
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
