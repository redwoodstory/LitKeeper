from __future__ import annotations
from flask import Blueprint, request, jsonify, send_from_directory, current_app, abort, Flask
from flask.typing import ResponseReturnValue
from app.services import download_story_and_create_files, log_error, log_url, generate_cover_image, extract_cover_from_epub, get_library_data
from app.utils import get_epub_directory, get_html_directory, get_cover_directory
from app.validators import StoryDownloadRequest, StoryMetadataUpdate
from app.services.story_downloader import download_story
from app.services.metadata_refresh_service import MetadataRefreshService
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

@api.route("/preview", methods=['POST'])
def preview_story() -> ResponseReturnValue:
    try:
        data = request.get_json()
        url = data.get('url', '')
        formats = data.get('format', ['epub'])

        validated = StoryDownloadRequest(url=url, format=formats)

    except ValidationError as e:
        error_details = e.errors()[0]
        error_msg = f"{error_details['loc'][0]}: {error_details['msg']}"
        log_error(f"Validation error: {error_msg}\nData: {request.get_data(as_text=True)}")
        return jsonify({
            "success": False,
            "message": error_msg
        }), 400

    log_url(validated.url)

    try:
        from app.services import story_processor
        story_data = download_story(validated.url)
        story_content, title, author, category, tags, author_url, page_count = story_data

        if not story_content or not title:
            return jsonify({
                "success": False,
                "message": "Failed to extract story metadata"
            }), 500

        story_processor._story_cache[validated.url] = story_data

        return jsonify({
            "success": True,
            "metadata": {
                "url": validated.url,
                "title": title or "Unknown Title",
                "author": author or "Unknown Author",
                "category": category,
                "tags": tags or [],
                "author_url": author_url,
                "formats": validated.format
            }
        })

    except Exception as e:
        error_msg = f"Error previewing story: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while fetching story metadata"
        }), 500

@api.route("/save", methods=['POST'])
def save_story() -> ResponseReturnValue:
    try:
        data = request.get_json()
        validated = StoryMetadataUpdate(**data)

    except ValidationError as e:
        error_details = e.errors()[0]
        error_msg = f"{error_details['loc'][0]}: {error_details['msg']}"
        log_error(f"Validation error: {error_msg}\nData: {request.get_data(as_text=True)}")
        return jsonify({
            "success": False,
            "message": error_msg
        }), 400

    log_url(validated.url)

    try:
        from app.services.story_processor import save_story_with_metadata
        result = save_story_with_metadata(
            url=validated.url,
            formats=validated.formats,
            title=validated.title,
            author=validated.author,
            category=validated.category,
            tags=validated.tags
        )
        return jsonify(result.to_dict())

    except Exception as e:
        error_msg = f"Error saving story: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while saving the story"
        }), 500

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

@api.route("/metadata/search/<int:story_id>", methods=['POST'])
def search_metadata(story_id: int) -> ResponseReturnValue:
    try:
        service = MetadataRefreshService()
        result = service.search_for_story(story_id)
        return jsonify(result)
    except Exception as e:
        error_msg = f"Error searching for story metadata: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while searching for metadata"
        }), 500

@api.route("/metadata/refresh/<int:story_id>", methods=['POST'])
def refresh_metadata(story_id: int) -> ResponseReturnValue:
    try:
        data = request.get_json()
        url = data.get('url')
        method = data.get('method', 'manual')
        
        if not url:
            return jsonify({
                "success": False,
                "message": "URL is required"
            }), 400
        
        service = MetadataRefreshService()
        result = service.refresh_metadata_from_url(story_id, url, method)
        return jsonify(result)
    except Exception as e:
        error_msg = f"Error refreshing metadata: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while refreshing metadata"
        }), 500

@api.route("/metadata/missing", methods=['GET'])
def get_missing_metadata() -> ResponseReturnValue:
    try:
        from app.models import Story

        stories = Story.query.filter(Story.literotica_url.is_(None)).all()

        return jsonify({
            "success": True,
            "count": len(stories),
            "stories": [story.to_library_dict() for story in stories]
        })
    except Exception as e:
        error_msg = f"Error fetching missing metadata: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while fetching stories"
        }), 500

@api.route("/format/generate-epub/<int:story_id>", methods=['POST'])
def generate_epub_format(story_id: int) -> ResponseReturnValue:
    try:
        from app.services.format_generator import FormatGeneratorService
        from app.models import Story

        service = FormatGeneratorService()
        result = service.generate_epub_from_json(story_id)

        if result.get('success') and request.headers.get('HX-Request'):
            story = Story.query.get(story_id)
            if story:
                return jsonify({
                    "success": True,
                    "message": result.get('message'),
                    "story": story.to_library_dict()
                })

        return jsonify(result)
    except Exception as e:
        error_msg = f"Error generating EPUB format: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while generating EPUB format"
        }), 500

@api.route("/format/generate-html/<int:story_id>", methods=['POST'])
def generate_html_format(story_id: int) -> ResponseReturnValue:
    try:
        from app.services.format_generator import FormatGeneratorService
        from app.models import Story

        service = FormatGeneratorService()
        result = service.generate_html_from_url(story_id)

        if result.get('success') and request.headers.get('HX-Request'):
            story = Story.query.get(story_id)
            if story:
                return jsonify({
                    "success": True,
                    "message": result.get('message'),
                    "story": story.to_library_dict()
                })

        return jsonify(result)
    except Exception as e:
        error_msg = f"Error generating HTML format: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while generating HTML format"
        }), 500

@api.route("/format/generate-html-with-metadata/<int:story_id>", methods=['POST'])
def generate_html_with_metadata(story_id: int) -> ResponseReturnValue:
    try:
        from app.services.format_generator import FormatGeneratorService
        from app.models import Story
        
        data = request.get_json()
        url = data.get('url')
        method = data.get('method', 'manual')
        
        if not url:
            return jsonify({
                "success": False,
                "message": "URL is required"
            }), 400

        service = FormatGeneratorService()
        result = service.generate_html_with_metadata(story_id, url, method)

        if result.get('success') and request.headers.get('HX-Request'):
            story = Story.query.get(story_id)
            if story:
                return jsonify({
                    "success": True,
                    "message": result.get('message'),
                    "fields_changed": result.get('fields_changed', []),
                    "story": story.to_library_dict()
                })

        return jsonify(result)
    except Exception as e:
        error_msg = f"Error generating HTML format with metadata: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while generating HTML format"
        }), 500
