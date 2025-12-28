from __future__ import annotations
from flask import Blueprint, render_template, request, send_from_directory, jsonify, abort
from flask.typing import ResponseReturnValue
from app.services import download_story_and_create_files, log_error
from app.services.system_checks import check_mount_warning, check_secret_key_warning
from app.utils import get_epub_directory, get_html_directory
from app.validators import StoryDownloadRequest, LibraryFilterRequest
from pydantic import ValidationError
import os
from datetime import datetime
import traceback
import json

library = Blueprint('library', __name__)

def get_library_data() -> list[dict]:
    epub_directory = get_epub_directory()
    html_directory = get_html_directory()

    os.makedirs(epub_directory, exist_ok=True)
    os.makedirs(html_directory, exist_ok=True)

    epub_files = {f.replace('.epub', ''): f for f in os.listdir(epub_directory)
                 if f.endswith('.epub') and f != 'cover.jpg'}

    story_files = {}
    for f in os.listdir(html_directory):
        if f.endswith('.json'):
            title = f.replace('.json', '')
            story_files[title] = f
        elif f.endswith('.html'):
            title = f.replace('.html', '')
            if title not in story_files:
                story_files[title] = f

    all_titles = set(epub_files.keys()) | set(story_files.keys())
    stories = []

    for filename_base in sorted(all_titles):
        story = {"formats": [], "filename_base": filename_base}

        display_title = filename_base
        author = None
        category = None
        tags = []
        cover = None

        if filename_base in story_files and story_files[filename_base].endswith('.json'):
            try:
                json_path = os.path.join(html_directory, story_files[filename_base])
                with open(json_path, 'r', encoding='utf-8') as f:
                    story_data = json.load(f)
                    display_title = story_data.get('title', filename_base)
                    author = story_data.get('author')
                    category = story_data.get('category')
                    tags = story_data.get('tags', [])
                    cover = story_data.get('cover')
                    source_url = story_data.get('source_url')
                    author_url = story_data.get('author_url')
            except:
                pass

        story["title"] = display_title
        if author:
            story["author"] = author
        if category:
            story["category"] = category
        if tags:
            story["tags"] = tags
        if cover:
            story["cover"] = cover
        if 'source_url' in locals() and source_url:
            story["source_url"] = source_url
        if 'author_url' in locals() and author_url:
            story["author_url"] = author_url

        if filename_base in epub_files:
            epub_path = os.path.join(epub_directory, epub_files[filename_base])
            story["formats"].append("epub")
            story["epub_file"] = epub_files[filename_base]
            story["created_at"] = datetime.fromtimestamp(
                os.path.getmtime(epub_path)
            ).isoformat()
            story["size"] = os.path.getsize(epub_path)

        if filename_base in story_files:
            story_path = os.path.join(html_directory, story_files[filename_base])
            story["formats"].append("html")
            story["html_file"] = filename_base + ".html"
            if "created_at" not in story:
                story["created_at"] = datetime.fromtimestamp(
                    os.path.getmtime(story_path)
                ).isoformat()

        stories.append(story)

    stories.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return stories

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
            secret_key_warning = check_secret_key_warning()
            return render_template("index.html", stories=stories, categories=categories, view='detailed', error=error_msg, mount_warning=mount_warning, secret_key_warning=secret_key_warning, enable_library=enable_library)

    enable_library = os.getenv('ENABLE_LIBRARY', 'true').lower() == 'true'

    try:
        stories = get_library_data() if enable_library else []
        categories = sorted(set(s.get('category') for s in stories if s.get('category'))) if enable_library else []
        mount_warning = check_mount_warning()
        secret_key_warning = check_secret_key_warning()
        return render_template("index.html", stories=stories, categories=categories, mount_warning=mount_warning, secret_key_warning=secret_key_warning, enable_library=enable_library)
    except Exception as e:
        log_error(f"Error loading index: {str(e)}\n{traceback.format_exc()}")
        return render_template("index.html", stories=[], categories=[], mount_warning={"show_warning": False}, secret_key_warning=False, enable_library=enable_library)

@library.route("/library/filter", methods=["GET"])
def filter_library() -> ResponseReturnValue:
    try:
        validated = LibraryFilterRequest(
            search=request.args.get('search', ''),
            category=request.args.get('category', 'all'),
            view=request.args.get('view', 'detailed')
        )

        stories = get_library_data()

        if validated.search:
            stories = [s for s in stories if
                      validated.search in s.get('title', '').lower() or
                      validated.search in s.get('author', '').lower()]

        if validated.category and validated.category != 'all':
            if validated.category == 'uncategorized':
                stories = [s for s in stories if not s.get('category')]
            else:
                stories = [s for s in stories if s.get('category') == validated.category]

        return render_template("_library_content.html", stories=stories, view=validated.view)
    except ValidationError as e:
        log_error(f"Validation error in library filter: {str(e)}")
        return render_template("_library_content.html", stories=[], view='detailed')
    except Exception as e:
        log_error(f"Error filtering library: {str(e)}")
        return render_template("_library_content.html", stories=[], view='detailed')

@library.route("/read/<filename>")
def read_story(filename: str) -> ResponseReturnValue:
    if '..' in filename or filename.startswith('/'):
        log_error(f"Attempted path traversal in read: {filename}")
        abort(404)

    html_directory = get_html_directory()

    if filename.endswith('.html'):
        json_filename = filename.replace('.html', '.json')
    elif filename.endswith('.json'):
        json_filename = filename
    else:
        abort(404)

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

@library.route("/sw.js")
def service_worker() -> ResponseReturnValue:
    static_directory = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")
    return send_from_directory(
        static_directory,
        "sw.js",
        mimetype='application/javascript'
    )
