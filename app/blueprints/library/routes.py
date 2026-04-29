from __future__ import annotations
from flask import Blueprint, render_template, request, send_from_directory, jsonify, abort, make_response
from flask.typing import ResponseReturnValue
from app.models import Story
from app.services import download_story_and_create_files, log_error, log_action, get_library_data
from app.services.epub_service import EpubService
from app.services.system_checks import check_mount_warning, check_legacy_mounts
from app.utils import get_html_directory, get_epub_directory
from app.utils.security import validate_file_in_directory
from app.validators import StoryDownloadRequest, LibraryFilterRequest
from pydantic import ValidationError
import os
import traceback
import json

library = Blueprint('library', __name__)

@library.route("/", methods=["GET", "POST"])
def index() -> ResponseReturnValue:
    if request.method == "POST":
        try:
            url = request.form.get("url", "")
            formats = ["epub", "html"]

            validated = StoryDownloadRequest(url=url, wait=True, format=formats)
            result = download_story_and_create_files(validated.url, validated.format)
            return jsonify(result.to_dict())

        except ValidationError as e:
            error_details = e.errors()[0]
            error_msg = f"{error_details['loc'][0]}: {error_details['msg']}"
            log_error(f"Validation error on index form: {error_msg}")
            enable_library = os.getenv('ENABLE_LIBRARY', 'true').lower() == 'true'
            stories = get_library_data() if enable_library else []
            categories = sorted(set(s.get('category') for s in stories if s.get('category'))) if enable_library else []
            mount_warning = check_mount_warning()
            legacy_info = check_legacy_mounts()
            return render_template("index.html", stories=stories, categories=categories, error=error_msg, mount_warning=mount_warning, legacy_info=legacy_info, enable_library=enable_library)

    enable_library = os.getenv('ENABLE_LIBRARY', 'true').lower() == 'true'

    try:
        from app.services.migration.file_scanner import FileScanner
        from app.services.migration.sync_checker import SyncChecker
        from app.models import Story
        from flask import current_app

        mount_warning = check_mount_warning()
        legacy_info = check_legacy_mounts()

        sync_status = None

        if enable_library:
            sync_checker = SyncChecker()
            sync_status = sync_checker.check_sync()
            
            log_action(f"[BANNER] Sync check: in_sync={sync_status['in_sync']}, orphaned_files={sync_status['orphaned_files_count']}, orphaned_db={sync_status['orphaned_db_count']}")
            
            if not sync_status['in_sync'] and hasattr(current_app, 'automation'):
                log_action(f"[BANNER] Automation state: has_completed_first_run={current_app.automation.has_completed_first_run}, is_processing={current_app.automation.is_processing}")
                
                if current_app.automation.is_processing:
                    log_action("[BANNER] Automation is currently processing, hiding banner")
                    sync_status = None
                elif sync_status['orphaned_files_count'] > 0:
                    log_action(f"[BANNER] Found {sync_status['orphaned_files_count']} orphaned files, triggering automation and hiding banner")
                    current_app.automation.trigger_immediate_run()
                    sync_status = None
                else:
                    log_action("[BANNER] Only orphaned DB records (no files to import), showing banner")

        stories = get_library_data() if enable_library else []
        categories = sorted(set(s.get('category') for s in stories if s.get('category'))) if enable_library else []

        open_modal_story = None
        open_modal_id = request.args.get('open_modal', type=int)
        if open_modal_id and enable_library:
            _s = Story.query.get(open_modal_id)
            if _s:
                open_modal_story = {
                    'id': _s.id,
                    'title': _s.title,
                    'author': {'name': _s.author.name, 'literotica_url': _s.author.literotica_url} if _s.author else None,
                    'author_url': _s.author.literotica_url if _s.author else None,
                    'category': {'name': _s.category.name} if _s.category else None,
                    'tags': [tag.name for tag in _s.tags],
                    'cover': _s.cover_filename,
                    'formats': [fmt.format_type for fmt in _s.formats],
                    'filename_base': _s.filename_base,
                    'html_file': f"{_s.filename_base}.html",
                    'epub_file': os.path.basename(next((f.file_path for f in _s.formats if f.format_type == 'epub'), '')) or None,
                    'source_url': _s.literotica_url,
                    'series_url': _s.literotica_series_url,
                    'page_count': _s.literotica_page_count,
                    'word_count': _s.word_count,
                    'chapter_count': _s.chapter_count,
                    'size': next((f.file_size for f in _s.formats if f.format_type == 'epub'), None),
                    'created_at': _s.created_at,
                    'auto_update_enabled': _s.auto_update_enabled,
                    'is_series': bool(_s.literotica_series_url and _s.chapter_count > 1),
                    'description': _s.description,
                }

        return render_template("index.html", stories=stories, categories=categories, mount_warning=mount_warning, legacy_info=legacy_info, enable_library=enable_library, sync_status=sync_status, open_modal_story=open_modal_story)
    except Exception as e:
        log_error(f"Error loading index: {str(e)}\n{traceback.format_exc()}")
        return render_template("index.html", stories=[], categories=[], mount_warning={"show_warning": False}, legacy_info={"has_legacy_mounts": False}, enable_library=enable_library)

@library.route('/sync-banner')
def sync_banner():
    """Return just the sync banner HTML (for dynamic loading via HTMX)."""
    from app.services.migration.sync_checker import SyncChecker
    from flask import current_app

    enable_library = os.getenv('ENABLE_LIBRARY', 'true').lower() == 'true'

    if not enable_library:
        return '', 204

    sync_checker = SyncChecker()
    sync_status = sync_checker.check_sync()

    log_action(f"[BANNER] Sync check: in_sync={sync_status['in_sync']}, orphaned_files={sync_status['orphaned_files_count']}, orphaned_db={sync_status['orphaned_db_count']}")

    if not sync_status['in_sync'] and hasattr(current_app, 'automation'):
        log_action(f"[BANNER] Automation state: has_completed_first_run={current_app.automation.has_completed_first_run}, is_processing={current_app.automation.is_processing}")

        if current_app.automation.is_processing:
            log_action("[BANNER] Automation is currently processing, hiding banner")
            sync_status = None
        elif sync_status['orphaned_files_count'] > 0:
            log_action(f"[BANNER] Found {sync_status['orphaned_files_count']} orphaned files, triggering automation and hiding banner")
            current_app.automation.trigger_immediate_run()
            sync_status = None
        else:
            log_action("[BANNER] Only orphaned DB records (no files to import), showing banner")

    if not sync_status or sync_status['in_sync']:
        return '', 204

    return render_template("partials/sync_banner_warning.html", sync_status=sync_status)

@library.route('/admin/sync/full', methods=['POST'])
def sync_full() -> ResponseReturnValue:
    from app.services.migration.sync_checker import SyncChecker
    try:
        checker = SyncChecker()
        result = checker.full_sync()
        log_action(f"[SYNC] Full sync completed: {result['records_cleaned']} records cleaned, {result['files_added']} files added.")
        return '', 200
    except Exception as e:
        log_error(f"Error during full sync: {str(e)}\n{traceback.format_exc()}")
        return '', 500

@library.route("/library/filter", methods=["GET"])
def filter_library() -> ResponseReturnValue:
    try:
        raw_queue_only = request.args.get('queue_only')
        log_action(f"[FILTER DEBUG] raw queue_only='{raw_queue_only}', bool={raw_queue_only == 'true'}")
        validated = LibraryFilterRequest(
            search=request.args.get('search', ''),
            category=request.args.get('category', 'all'),
            sort_by=request.args.get('sort_by', 'date'),
            sort_order=request.args.get('sort_order', 'desc'),
            queue_only=raw_queue_only == 'true'
        )

        stories = get_library_data()

        if validated.search:
            search_term = validated.search.lower()
            scored_stories = []

            for story in stories:
                score = 0
                title = story.get('title', '').lower()
                author = story.get('author', '').lower()
                category = story.get('category', '').lower()
                tags = [tag.lower() for tag in story.get('tags', [])]

                if search_term in title:
                    score += 100
                if search_term in author:
                    score += 50
                if search_term in category:
                    score += 25
                if any(search_term in tag for tag in tags):
                    score += 10

                if score > 0:
                    scored_stories.append((score, story))

            scored_stories.sort(key=lambda x: x[0], reverse=True)
            stories = [story for _, story in scored_stories]

        if validated.category and validated.category != 'all':
            if validated.category == 'uncategorized':
                stories = [s for s in stories if not s.get('category')]
            else:
                stories = [s for s in stories if s.get('category') == validated.category]

        if validated.queue_only:
            stories = [s for s in stories if s.get('in_queue')]

        def get_sort_key(story: dict) -> tuple:
            if validated.sort_by == 'name':
                return (story.get('title', '').lower(),)
            elif validated.sort_by == 'author':
                return (story.get('author', '').lower(),)
            elif validated.sort_by == 'category':
                return (story.get('category', '').lower(),)
            elif validated.sort_by == 'length':
                return (story.get('word_count', 0),)
            elif validated.sort_by == 'rating':
                return (story.get('rating') or 0,)
            elif validated.sort_by == 'last_opened':
                # Stories never opened (None) should sort last when descending
                return (story.get('last_opened_at') or '',)
            else:
                return (story.get('created_at', ''),)

        if validated.sort_by == 'length':
            log_action(f"[SORT DEBUG] Sorting by length, order={validated.sort_order}, reverse={validated.sort_order == 'desc'}")
            sample_stories = stories[:3] if len(stories) >= 3 else stories
            for s in sample_stories:
                log_action(f"[SORT DEBUG] Sample: {s.get('title')} - word_count={s.get('word_count')}")

        stories.sort(key=get_sort_key, reverse=(validated.sort_order == 'desc'))

        if validated.sort_by == 'length':
            sample_stories = stories[:3] if len(stories) >= 3 else stories
            for s in sample_stories:
                log_action(f"[SORT DEBUG] After sort: {s.get('title')} - word_count={s.get('word_count')}")

        return render_template("_library_content.html", stories=stories, queue_only=validated.queue_only)
    except ValidationError as e:
        log_error(f"Validation error in library filter: {str(e)}")
        return render_template("_library_content.html", stories=[], queue_only=False)
    except Exception as e:
        log_error(f"Error filtering library: {str(e)}")
        return render_template("_library_content.html", stories=[], queue_only=False)

@library.route("/read/<filename>")
def read_story(filename: str) -> ResponseReturnValue:
    if not filename:
        abort(404)

    if filename.endswith('.html'):
        filename_base = filename[:-5]
    elif filename.endswith('.json'):
        filename_base = filename[:-5]
    else:
        abort(404)

    if not validate_file_in_directory(get_html_directory(), filename_base):
        log_error(f"Path traversal blocked in read: {filename}")
        abort(403)

    # Look up the story by filename_base, then get the actual file path from StoryFormat.
    from app.models import StoryFormat
    story_db = Story.query.filter_by(filename_base=filename_base).first()
    if not story_db:
        abort(404)

    json_fmt = StoryFormat.query.filter_by(story_id=story_db.id, format_type='json').first()
    if not json_fmt or not os.path.exists(json_fmt.file_path):
        abort(404)

    try:
        with open(json_fmt.file_path, 'r', encoding='utf-8') as f:
            story_data = json.load(f)

        progress = EpubService.get_reading_progress(story_db.id)

        from datetime import datetime
        from app.models import db
        story_db.last_opened_at = datetime.utcnow()
        db.session.commit()

        if story_db.description and not story_data.get('description'):
            story_data['description'] = story_db.description

        target_chapter = request.args.get('chapter', type=int)
        target_para = request.args.get('para', type=int)
        epub_fmt = StoryFormat.query.filter_by(story_id=story_db.id, format_type='epub').first()
        epub_filename = os.path.basename(epub_fmt.file_path) if epub_fmt else None
        return render_template('reader.html', story=story_data, story_id=story_db.id, progress=progress,
                               target_chapter=target_chapter, target_para=target_para,
                               epub_filename=epub_filename)

    except Exception as e:
        log_error(f"Error loading story {filename_base}: {str(e)}\n{traceback.format_exc()}")
        abort(500)

@library.route("/download/<format_type>/<filename>")
def download_story(format_type: str, filename: str) -> ResponseReturnValue:
    if not filename or format_type not in ['html', 'epub']:
        abort(404)

    # Extract filename_base from the URL slug (strip any extension).
    for ext in ('.html', '.json', '.epub'):
        if filename.endswith(ext):
            filename_base = filename[:-len(ext)]
            break
    else:
        abort(404)

    if not validate_file_in_directory(get_html_directory(), filename_base):
        log_error(f"Path traversal blocked in download: {filename}")
        abort(403)

    from app.models import StoryFormat
    story_db = Story.query.filter_by(filename_base=filename_base).first()
    if not story_db:
        abort(404)

    if format_type == 'html':
        json_fmt = StoryFormat.query.filter_by(story_id=story_db.id, format_type='json').first()
        if not json_fmt or not os.path.exists(json_fmt.file_path):
            abort(404)

        try:
            with open(json_fmt.file_path, 'r', encoding='utf-8') as f:
                story_data = json.load(f)

            html_content = render_template('download.html', story=story_data)
            response = make_response(html_content)
            response.headers['Content-Type'] = 'text/html; charset=utf-8'
            safe_title = "".join(c for c in story_data.get('title', 'story') if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_title = safe_title.replace(' ', '_')
            response.headers['Content-Disposition'] = f'attachment; filename="{safe_title}.html"'
            return response

        except Exception as e:
            log_error(f"Error creating HTML download for {filename_base}: {str(e)}\n{traceback.format_exc()}")
            abort(500)

    elif format_type == 'epub':
        epub_fmt = StoryFormat.query.filter_by(story_id=story_db.id, format_type='epub').first()
        if not epub_fmt or not os.path.exists(epub_fmt.file_path):
            abort(404)

        try:
            epub_directory = os.path.dirname(epub_fmt.file_path)
            epub_filename = os.path.basename(epub_fmt.file_path)
            return send_from_directory(epub_directory, epub_filename, as_attachment=True, mimetype='application/epub+zip')
        except Exception as e:
            log_error(f"Error sending EPUB download for {filename_base}: {str(e)}\n{traceback.format_exc()}")
            abort(500)

