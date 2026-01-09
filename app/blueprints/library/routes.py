from __future__ import annotations
from flask import Blueprint, render_template, request, send_from_directory, jsonify, abort, make_response
from flask.typing import ResponseReturnValue
from app.services import download_story_and_create_files, log_error, log_action, get_library_data
from app.services.system_checks import check_mount_warning
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
            formats = request.form.getlist("format")
            if not formats:
                formats = ["epub"]

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
            return render_template("index.html", stories=stories, categories=categories, error=error_msg, mount_warning=mount_warning, enable_library=enable_library)

    enable_library = os.getenv('ENABLE_LIBRARY', 'true').lower() == 'true'

    try:
        from app.services.migration.file_scanner import FileScanner
        from app.services.migration.sync_checker import SyncChecker
        from app.models import Story
        from flask import current_app

        mount_warning = check_mount_warning()

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

        return render_template("index.html", stories=stories, categories=categories, mount_warning=mount_warning, enable_library=enable_library, sync_status=sync_status)
    except Exception as e:
        log_error(f"Error loading index: {str(e)}\n{traceback.format_exc()}")
        return render_template("index.html", stories=[], categories=[], mount_warning={"show_warning": False}, enable_library=enable_library)

@library.route("/library/filter", methods=["GET"])
def filter_library() -> ResponseReturnValue:
    try:
        validated = LibraryFilterRequest(
            search=request.args.get('search', ''),
            category=request.args.get('category', 'all'),
            sort_by=request.args.get('sort_by', 'date'),
            sort_order=request.args.get('sort_order', 'desc')
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

        def get_sort_key(story: dict) -> tuple:
            if validated.sort_by == 'name':
                return (story.get('title', '').lower(),)
            elif validated.sort_by == 'author':
                return (story.get('author', '').lower(),)
            elif validated.sort_by == 'category':
                return (story.get('category', '').lower(),)
            elif validated.sort_by == 'length':
                return (story.get('word_count', 0),)
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

        return render_template("_library_content.html", stories=stories)
    except ValidationError as e:
        log_error(f"Validation error in library filter: {str(e)}")
        return render_template("_library_content.html", stories=[])
    except Exception as e:
        log_error(f"Error filtering library: {str(e)}")
        return render_template("_library_content.html", stories=[])

@library.route("/read/<filename>")
def read_story(filename: str) -> ResponseReturnValue:
    if not filename:
        abort(404)

    html_directory = get_html_directory()

    if filename.endswith('.html'):
        json_filename = filename.replace('.html', '.json')
    elif filename.endswith('.json'):
        json_filename = filename
    else:
        abort(404)

    if not validate_file_in_directory(html_directory, json_filename):
        log_error(f"Path traversal blocked in read: {filename}")
        abort(403)

    json_path = os.path.join(html_directory, json_filename)

    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                story_data = json.load(f)

            return render_template('reader.html', story=story_data)

        except Exception as e:
            log_error(f"Error loading story {json_filename}: {str(e)}\n{traceback.format_exc()}")
            abort(500)

    elif filename.endswith('.html') and os.path.exists(os.path.join(html_directory, filename)):
        return send_from_directory(html_directory, filename)

    else:
        abort(404)

@library.route("/download/<format_type>/<filename>")
def download_story(format_type: str, filename: str) -> ResponseReturnValue:
    if not filename:
        abort(404)

    if format_type not in ['html', 'epub']:
        abort(404)

    html_directory = get_html_directory()

    if format_type == 'html':
        if filename.endswith('.html'):
            json_filename = filename.replace('.html', '.json')
        elif filename.endswith('.json'):
            json_filename = filename
        else:
            abort(404)

        if not validate_file_in_directory(html_directory, json_filename):
            log_error(f"Path traversal blocked in download: {filename}")
            abort(403)

        json_path = os.path.join(html_directory, json_filename)

        if not os.path.exists(json_path):
            abort(404)

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                story_data = json.load(f)

            html_content = render_template('download.html', story=story_data)

            response = make_response(html_content)
            response.headers['Content-Type'] = 'text/html; charset=utf-8'

            safe_title = "".join(c for c in story_data.get('title', 'story') if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_title = safe_title.replace(' ', '_')
            response.headers['Content-Disposition'] = f'attachment; filename="{safe_title}.html"'

            return response

        except Exception as e:
            log_error(f"Error creating HTML download for {json_filename}: {str(e)}\n{traceback.format_exc()}")
            abort(500)

    elif format_type == 'epub':
        epub_directory = get_epub_directory()

        if filename.endswith('.epub'):
            epub_filename = filename
        elif filename.endswith('.html'):
            epub_filename = filename.replace('.html', '.epub')
        elif filename.endswith('.json'):
            epub_filename = filename.replace('.json', '.epub')
        else:
            abort(404)

        if not validate_file_in_directory(epub_directory, epub_filename):
            log_error(f"Path traversal blocked in download: {filename}")
            abort(403)

        epub_path = os.path.join(epub_directory, epub_filename)

        if not os.path.exists(epub_path):
            abort(404)

        try:
            return send_from_directory(epub_directory, epub_filename, as_attachment=True, mimetype='application/epub+zip')
        except Exception as e:
            log_error(f"Error sending EPUB download for {epub_filename}: {str(e)}\n{traceback.format_exc()}")
            abort(500)

@library.route("/sw.js")
def service_worker() -> ResponseReturnValue:
    static_directory = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")
    return send_from_directory(
        static_directory,
        "sw.js",
        mimetype='application/javascript'
    )
