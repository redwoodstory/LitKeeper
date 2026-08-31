from __future__ import annotations
from typing import Optional
import traceback
import os
import shutil
import glob
from datetime import datetime
from app.utils import get_epub_directory, get_html_directory, get_archive_directory, sanitize_filename
from .story_downloader import download_story, extract_chapter_titles, split_story_chapters, CHAPTER_SENTINEL
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
    story_stats: Optional[dict] = None,
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
        _apply_scraped_stats(duplicate, story_stats)
        _apply_community_stats(duplicate, source_url)
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

    _apply_scraped_stats(story, story_stats)
    _apply_community_stats(story, source_url)
    _record_seen_urls(story)

    return story


def _apply_scraped_stats(story, stats: Optional[dict]) -> None:
    """Apply freshly-scraped community stats from the story page itself.

    Takes priority over the bundled dataset lookup in _apply_community_stats,
    which only fills fields still left None after this runs.
    """
    if not stats:
        return
    if stats.get('score') is not None:
        story.literotica_score = stats['score']
    if stats.get('views') is not None:
        story.literotica_views = stats['views']
    if stats.get('favorites') is not None:
        story.literotica_favorites = stats['favorites']
    if stats.get('comments') is not None:
        story.literotica_comments = stats['comments']


def _apply_community_stats(story, url: Optional[str]) -> None:
    """Populate community stats from custom_url_dataset.db if available and not already set."""
    if not url:
        return
    try:
        from flask import current_app
        import sqlite3 as _sqlite3
        db_path = os.path.join(current_app.root_path, 'data', 'custom_url_dataset.db')
        if not os.path.exists(db_path):
            return
        with _sqlite3.connect(db_path) as con:
            row = con.execute(
                "SELECT score, views, favorites, comments FROM stories WHERE url = ?", (url,)
            ).fetchone()
        if not row:
            return
        if story.literotica_score is None and row[0] is not None:
            story.literotica_score = float(row[0])
        if story.literotica_views is None and row[1] is not None:
            story.literotica_views = int(row[1])
        if story.literotica_favorites is None and row[2] is not None:
            story.literotica_favorites = int(row[2])
        if story.literotica_comments is None and row[3] is not None:
            story.literotica_comments = int(row[3])
    except Exception as e:
        log_error(f"[community_stats] Could not apply stats for {url}: {e}")


def _record_seen_urls(story) -> None:
    """
    Record every individual Literotica chapter URL consumed by this story into
    seen_literotica_urls so that author re-scans never re-queue already-downloaded
    content — even when a chapter URL appears that differs from the one originally
    used to initiate the download.

    For standalone stories: records story.literotica_url.
    For series: also calls SeriesPageChecker to enumerate all chapter URLs and
    records each one (uses the same fast JSON API endpoint already used at download
    time, so no extra HTML scraping is needed).
    """
    from app.models import SeenLiteroticaUrl
    from app.models.base import db

    if not story or not story.literotica_url:
        return

    urls_to_record: list[str] = [story.literotica_url]

    if story.literotica_series_url:
        urls_to_record.append(story.literotica_series_url)
        try:
            from .series_page_checker import SeriesPageChecker
            checker = SeriesPageChecker()
            series_info = checker.check_series_parts(story.literotica_series_url)
            if series_info and series_info.get('parts'):
                for part in series_info['parts']:
                    part_url = part.get('url', '').strip()
                    if part_url:
                        urls_to_record.append(part_url)
        except Exception as e:
            log_error(f"[seen_urls] Could not enumerate series parts for {story.literotica_series_url}: {e}")

    for url in urls_to_record:
        try:
            existing = SeenLiteroticaUrl.query.filter_by(url=url).first()
            if not existing:
                db.session.add(SeenLiteroticaUrl(url=url, story_id=story.id))
        except Exception as e:
            log_error(f"[seen_urls] Failed to record URL {url}: {e}")

    try:
        db.session.flush()
    except Exception as e:
        log_error(f"[seen_urls] Flush failed: {e}")


def link_story_formats(story) -> None:
    """
    Create or update StoryFormat records for files on disk.
    Canonical path is "{story.id}_{story.filename_base}.epub/.json". If only the
    legacy "{story.filename_base}.epub/.json" exists (no ID prefix), the file is
    renamed to the canonical path before linking.
    """
    import json as _json
    from app.models import StoryFormat
    from app.models.base import db

    file_base = f"{story.id}_{story.filename_base}"

    # --- EPUB ---
    epub_path = os.path.join(get_epub_directory(), f"{file_base}.epub")
    old_epub_path = os.path.join(get_epub_directory(), f"{story.filename_base}.epub")
    if not os.path.exists(epub_path) and os.path.exists(old_epub_path):
        try:
            os.rename(old_epub_path, epub_path)
            log_action(f"Renamed legacy EPUB for story {story.id}: {story.filename_base}.epub → {file_base}.epub")
        except Exception as e:
            log_error(f"Failed to rename legacy EPUB for story {story.id}: {e}")

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

    # --- JSON ---
    json_path = os.path.join(get_html_directory(), f"{file_base}.json")
    old_json_path = os.path.join(get_html_directory(), f"{story.filename_base}.json")
    if not os.path.exists(json_path) and os.path.exists(old_json_path):
        try:
            os.rename(old_json_path, json_path)
            log_action(f"Renamed legacy JSON for story {story.id}: {story.filename_base}.json → {file_base}.json")
        except Exception as e:
            log_error(f"Failed to rename legacy JSON for story {story.id}: {e}")

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
    story_description: Optional[str] = None,
    all_authors: Optional[list[str]] = None,
    all_tags: Optional[list[str]] = None,
    story_stats: Optional[dict] = None,
) -> dict:
    """
    Get/create the story DB record first (to obtain a stable ID), then write files
    named "{story.id}_{story.filename_base}.epub/.json" so each file is unambiguously
    tied to its database record regardless of title changes.
    """
    try:
        chapter_count = max(len(split_story_chapters(story_content)) - 1, 1) if story_content else 1
        word_count = len(story_content.split()) if story_content else 0

        # Determine display author for files/cover — show "Multiple Authors" when
        # there are genuinely different authors across combined stories.
        display_author = story_author
        if all_authors and len(set(all_authors)) > 1:
            display_author = "Multiple Authors"

        # Use the combined/aggregated tags if provided, otherwise fall back to
        # the primary story's tags.
        tags_for_files = all_tags if all_tags is not None else story_tags

        # 1. DB first — get or create story record to obtain a stable story.id.
        story = None
        try:
            story = _get_or_create_story(
                story_title=story_title,
                story_author=display_author,
                story_category=story_category,
                story_tags=tags_for_files,
                source_url=source_url,
                author_url=author_url if display_author == story_author else None,
                page_count=page_count,
                series_url=series_url,
                chapter_count=chapter_count,
                word_count=word_count,
                story_description=story_description,
                story_stats=story_stats,
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
                display_author,
                story_content,
                get_epub_directory(),
                story_category=story_category,
                story_tags=tags_for_files,
                story_description=story_description,
                filename_base=file_base,
                all_authors=all_authors,
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
                display_author,
                story_content,
                get_html_directory(),
                story_category=story_category,
                story_tags=tags_for_files,
                chapter_titles=chapter_titles if chapter_titles else None,
                source_url=source_url,
                author_url=author_url,
                page_count=page_count,
                filename_base=file_base,
                story_description=story_description,
                all_authors=all_authors,
            )
            created_files.append(f"HTML: {html_file_name.split('/')[-1]}")
            log_action(f"Created HTML: {html_file_name}")

        # 5. Link file paths to StoryFormat records.
        if story is not None:
            try:
                link_story_formats(story)
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
            'formats_str': formats_str,
            'story_id': story.id if story is not None else None,
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
            story_content, _, _, _, _, story_author_url, story_pages, series_url, _, story_stats = _story_cache[url]
            del _story_cache[url]
        else:
            story_content, _, _, _, _, story_author_url, story_pages, series_url, _, story_stats = download_story(url)

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
            series_url=series_url,
            story_stats=story_stats
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

def _mark_story_as_custom(story) -> None:
    """Flag a story as user-authored: no Literotica source to poll or refresh against."""
    from app.models.base import db

    story.source_type = 'custom'
    story.auto_update_enabled = False
    story.auto_refresh_excluded = True
    story.auto_refresh_exclusion_reason = "Custom story — no external source"
    story.auto_refresh_exclusion_type = 'custom'
    db.session.commit()


def _expand_line_breaks_to_paragraphs(raw_content: str) -> str:
    """
    Treat every line break as a paragraph break. Downstream rendering only splits
    paragraphs on a blank line ("\n\n"), but a writer pasting from a normal text
    editor hits Enter once per paragraph, not twice — without this, consecutive
    lines collapse into a single run-on paragraph.
    """
    lines = [line.strip() for line in raw_content.split('\n')]
    lines = [line for line in lines if line]
    return '\n\n'.join(lines)


def _normalize_custom_story_content(raw_content: str, story_title: str) -> str:
    """
    Wrap plain user-pasted text in the same CHAPTER_SENTINEL format the Literotica
    scraper produces, so downstream chapter parsing (which treats content before the
    first sentinel as a droppable preamble, not a chapter) doesn't silently discard
    a chapter-1 body that has no explicit "Chapter 1:" heading — the normal case for
    a single-chapter paste. Chapter 1's title mirrors what a scraped standalone story
    gets (the story's own title), matching the heading real Literotica downloads show.
    """
    raw_content = _expand_line_breaks_to_paragraphs(raw_content)
    segments = split_story_chapters(raw_content)

    normalized_parts = []
    chapter_num = 1

    first = segments[0].strip()
    if first:
        normalized_parts.append(f"{CHAPTER_SENTINEL}CHAPTER:{chapter_num}{CHAPTER_SENTINEL}{story_title}\n\n{first}")
        chapter_num += 1

    for segment in segments[1:]:
        segment = segment.strip()
        if not segment:
            continue
        title_end = segment.find("\n\n")
        if title_end == -1:
            title, body = f"Chapter {chapter_num}", segment
        else:
            title, body = segment[:title_end].strip(), segment[title_end + 2:].strip()
        normalized_parts.append(f"{CHAPTER_SENTINEL}CHAPTER:{chapter_num}{CHAPTER_SENTINEL}{title}\n\n{body}")
        chapter_num += 1

    return ''.join(normalized_parts)


def save_custom_story_from_text(
    title: str,
    author: str,
    content: str,
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
    description: Optional[str] = None,
    formats: Optional[list[str]] = None,
) -> StoryProcessingResult:
    """Create a user-authored story from pasted text or an uploaded .txt file."""
    if formats is None:
        formats = ["epub"]

    try:
        log_action(f"Saving custom story: '{title}' by {author}")

        normalized_content = _normalize_custom_story_content(content, title)

        result = _create_story_files(
            story_content=normalized_content,
            story_title=title,
            story_author=author,
            story_category=category,
            story_tags=tags,
            source_url=None,
            author_url=None,
            page_count=None,
            formats=formats,
            story_description=description,
        )

        if not result['success']:
            return StoryProcessingResult(success=False, message=result['message'], error=result.get('error'))

        story_id = result.get('story_id')
        if story_id is not None:
            from app.models import Story
            story = Story.query.get(story_id)
            if story is not None and story.source_type != 'custom':
                _mark_story_as_custom(story)

        return StoryProcessingResult(
            success=True,
            message=result['message'],
            title=title,
            author=author,
            formats=formats,
            files=result['files'],
        )

    except Exception as e:
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return StoryProcessingResult(success=False, message=str(e), error=error_msg)


def save_custom_story_from_epub(
    title: str,
    author: str,
    uploaded_epub_path: str,
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
    description: Optional[str] = None,
) -> StoryProcessingResult:
    """Create a user-authored story from an uploaded .epub file (used as-is, not regenerated)."""
    from app.models.base import db
    from app.utils import story_json_path

    try:
        log_action(f"Saving custom story from uploaded EPUB: '{title}' by {author}")

        story = _get_or_create_story(
            story_title=title,
            story_author=author,
            story_category=category,
            story_tags=tags,
            source_url=None,
            author_url=None,
            page_count=None,
            series_url=None,
            chapter_count=1,
            word_count=0,
            story_description=description,
        )
        if story is None:
            return StoryProcessingResult(success=False, message="Library is disabled (ENABLE_LIBRARY=false)")

        db.session.commit()

        dest_path = os.path.join(get_epub_directory(), f"{story.id}_{story.filename_base}.epub")
        shutil.copyfile(uploaded_epub_path, dest_path)
        log_action(f"Copied uploaded EPUB for custom story {story.id} -> {dest_path}")

        link_story_formats(story)
        _mark_story_as_custom(story)

        from .format_generator import FormatGeneratorService
        json_result = FormatGeneratorService().generate_json_from_epub(story.id)
        if not json_result.get('success'):
            return StoryProcessingResult(
                success=False,
                message=json_result.get('message', 'Could not extract content from the uploaded EPUB'),
            )

        json_path = story_json_path(story.id, story.filename_base)
        if os.path.exists(json_path):
            import json as _json
            with open(json_path, 'r', encoding='utf-8') as f:
                story_data = _json.load(f)
            story.word_count = story_data.get('word_count') or 0
            story.chapter_count = story_data.get('chapter_count') or 1
            db.session.commit()

        created_files = ["EPUB: " + os.path.basename(dest_path), "JSON: " + os.path.basename(json_path)]

        return StoryProcessingResult(
            success=True,
            message=f"Successfully saved '{title}' by {author}",
            title=title,
            author=author,
            formats=['epub', 'json'],
            files=created_files,
        )

    except Exception as e:
        db.session.rollback()
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return StoryProcessingResult(success=False, message=str(e), error=error_msg)


def _chapters_to_editable_text(chapters: list[dict]) -> str:
    """
    Flatten a story's JSON chapters back into plain text a user can edit — the
    inverse of _normalize_custom_story_content. Chapter 1's title is dropped since
    it's always re-derived from the current story title on save; later chapters
    keep their "Chapter N: Title" heading line so re-submitting preserves the split.
    """
    lines: list[str] = []
    for idx, chapter in enumerate(chapters):
        if idx > 0:
            number = chapter.get('number', idx + 1)
            title = chapter.get('title', '') or f"Chapter {number}"
            lines.append(f"Chapter {number}: {title}")
        lines.extend(chapter.get('paragraphs', []))
    return '\n'.join(lines)


def get_custom_story_content(story_id: int) -> Optional[dict]:
    """Return the editable plain-text content for a custom story, or None if not found/not custom."""
    import json as _json
    from app.models import Story
    from app.utils import story_json_path

    story = Story.query.get(story_id)
    if not story or story.source_type != 'custom':
        return None

    json_path = story_json_path(story.id, story.filename_base)
    if not os.path.exists(json_path):
        return None

    with open(json_path, 'r', encoding='utf-8') as f:
        story_data = _json.load(f)

    return {
        'content': _chapters_to_editable_text(story_data.get('chapters', [])),
    }


def update_custom_story_content(story_id: int, content: str) -> StoryProcessingResult:
    """Regenerate a custom story's EPUB/JSON body from user-edited plain text, keeping its existing metadata."""
    from app.models import Story
    from app.models.base import db

    try:
        story = Story.query.get(story_id)
        if not story:
            return StoryProcessingResult(success=False, message="Story not found")
        if story.source_type != 'custom':
            return StoryProcessingResult(success=False, message="Only custom stories can have their content edited")

        content = _expand_line_breaks_to_paragraphs(content.replace('\r\n', '\n').replace('\r', '\n')).strip()
        if not content:
            return StoryProcessingResult(success=False, message="Story content is required")

        author_name = story.author.name if story.author else 'Unknown Author'
        category_name = story.category.name if story.category else None
        tags = [t.name for t in story.tags]

        normalized_content = _normalize_custom_story_content(content, story.title)

        archive_dir = get_archive_directory()
        os.makedirs(archive_dir, exist_ok=True)
        date_tag = datetime.utcnow().strftime('%Y%m%d')
        for fmt in list(story.formats):
            if fmt.file_path and os.path.exists(fmt.file_path):
                ext = os.path.splitext(fmt.file_path)[1]
                archive_path = os.path.join(archive_dir, f"{story.filename_base}_{date_tag}{ext}")
                shutil.copyfile(fmt.file_path, archive_path)

        file_base = f"{story.id}_{story.filename_base}"

        create_epub_file(
            story.title,
            author_name,
            normalized_content,
            get_epub_directory(),
            story_category=category_name,
            story_tags=tags,
            story_description=story.description,
            filename_base=file_base,
        )

        chapter_titles = extract_chapter_titles(normalized_content)
        create_html_file(
            story.title,
            author_name,
            normalized_content,
            get_html_directory(),
            story_category=category_name,
            story_tags=tags,
            chapter_titles=chapter_titles if chapter_titles else None,
            source_url=None,
            author_url=None,
            page_count=None,
            filename_base=file_base,
            story_description=story.description,
        )

        story.chapter_count = max(len(split_story_chapters(normalized_content)) - 1, 1)
        story.word_count = len(normalized_content.split())
        db.session.commit()

        link_story_formats(story)

        log_action(f"Updated content for custom story {story_id}: '{story.title}'")

        return StoryProcessingResult(
            success=True,
            message="Story content updated",
            title=story.title,
            author=author_name,
        )

    except Exception as e:
        db.session.rollback()
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return StoryProcessingResult(success=False, message="Failed to update story content", error=error_msg)


def download_story_and_create_files(
    url: str,
    formats: Optional[list[str]] = None,
    send_notifications: bool = True
) -> StoryProcessingResult:
    if formats is None:
        formats = ["epub"]

    try:
        log_action(f"Starting download: {url}")
        story_content, story_title, story_author, story_category, story_tags, story_author_url, story_pages, series_url, story_description, story_stats = download_story(url)

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
            story_description=story_description,
            story_stats=story_stats
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
