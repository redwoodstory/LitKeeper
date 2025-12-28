from __future__ import annotations
from flask import Blueprint, request, jsonify, send_from_directory, current_app, abort, Flask
from flask.typing import ResponseReturnValue
from app.services import download_story_and_create_files, log_error, log_url, generate_cover_image, extract_cover_from_epub
from app.utils import get_epub_directory, get_html_directory, get_cover_directory
from app.validators import StoryDownloadRequest
from pydantic import ValidationError
import os
from datetime import datetime
import traceback
import threading
import json
from typing import Optional

api = Blueprint('api', __name__, url_prefix='/api')

def background_process_wrapper(app: Flask, url: str, formats: list[str]) -> None:
    with app.app_context():
        download_story_and_create_files(url, formats, send_notifications=True)

@api.route("/download", methods=['GET', 'POST'])
def download() -> ResponseReturnValue:
    try:
        if request.method == 'POST':
            if request.is_json:
                data = request.get_json()
                url = data.get('url', '')
                wait = data.get('wait', True)
                if isinstance(wait, str):
                    wait = wait.lower() == 'true'
                formats = data.get('format', ['epub'])
            else:
                url = request.form.get('url', '')
                wait = request.form.get('wait', 'true').lower() == 'true'
                formats = request.form.getlist('format') or ['epub']
        else:
            url = request.args.get('url', '')
            wait = request.args.get('wait', 'true').lower() == 'true'
            formats_param = request.args.get('format', 'epub')
            formats = formats_param.split(',') if formats_param else ['epub']

        validated = StoryDownloadRequest(url=url, wait=wait, format=formats)

    except ValidationError as e:
        error_details = e.errors()[0]
        error_msg = f"{error_details['loc'][0]}: {error_details['msg']}"
        log_error(f"Validation error: {error_msg}\nRequest Method: {request.method}\nData: {request.get_data(as_text=True)}")
        return jsonify({
            "success": "false",
            "message": error_msg
        }), 400

    url = validated.url
    log_url(url)

    if not validated.wait:
        app = current_app._get_current_object()
        thread = threading.Thread(target=background_process_wrapper, args=(app, url, validated.format))
        thread.start()
        return jsonify({
            "success": "true",
            "message": "Request accepted, processing in background"
        })

    result = download_story_and_create_files(url, validated.format)
    return jsonify(result.to_dict())

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

@api.route("/library", methods=["GET"])
def get_library() -> ResponseReturnValue:
    try:
        stories = get_library_data()
        return jsonify({"stories": stories})
    except Exception as e:
        log_error(f"Error fetching library: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"stories": []})

@api.route("/cover/<filename>")
def get_cover(filename: str) -> ResponseReturnValue:
    from app.services import generate_cover_image, extract_cover_from_epub

    if '/..' in filename or filename.startswith('/') or filename.startswith('..'):
        log_error(f"Attempted path traversal in cover request: {filename}")
        abort(404)

    if not filename.endswith('.jpg'):
        abort(404)

    cover_directory = get_cover_directory()
    cover_path = os.path.join(cover_directory, filename)

    if os.path.exists(cover_path):
        return send_from_directory(cover_directory, filename, mimetype='image/jpeg')

    os.makedirs(cover_directory, exist_ok=True)

    sanitized_title = filename.replace('.jpg', '')
    html_directory = get_html_directory()
    epub_directory = get_epub_directory()
    json_path = os.path.join(html_directory, f"{sanitized_title}.json")
    epub_path = os.path.join(epub_directory, f"{sanitized_title}.epub")

    title = sanitized_title
    author = 'Unknown Author'

    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                story_data = json.load(f)
            title = story_data.get('title', sanitized_title)
            author = story_data.get('author', 'Unknown Author')
        except Exception as e:
            log_error(f"Error reading JSON metadata: {str(e)}")

    if os.path.exists(epub_path):
        try:
            if extract_cover_from_epub(epub_path, cover_path):
                return send_from_directory(cover_directory, filename, mimetype='image/jpeg')
        except Exception as e:
            log_error(f"Error extracting cover from EPUB: {str(e)}\n{traceback.format_exc()}")

    try:
        generate_cover_image(title, author, cover_path)
        return send_from_directory(cover_directory, filename, mimetype='image/jpeg')
    except Exception as e:
        log_error(f"Error generating cover: {str(e)}\n{traceback.format_exc()}")
        abort(500)
