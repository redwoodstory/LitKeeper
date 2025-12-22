from __future__ import annotations
from flask import Blueprint, request, render_template, send_from_directory, jsonify, abort, current_app, Response, Flask
from flask.typing import ResponseReturnValue
from .services import download_story, create_epub_file, create_html_file, log_error, log_action, log_url, send_notification, extract_chapter_titles
from .validators import StoryDownloadRequest, LibraryFilterRequest
from pydantic import ValidationError
import os
from datetime import datetime
import traceback
import threading
import json
import urllib.parse
from typing import Optional

main = Blueprint('main', __name__)

def background_process_url(app: Flask, url: str, formats: Optional[list[str]] = None) -> None:
    """Process URL in background without returning JSON response."""
    if formats is None:
        formats = ["epub"]
    try:
        with app.app_context():
            log_action(f"Starting download: {url}")
            story_content, story_title, story_author, story_category, story_tags = download_story(url)
            if not story_content:
                error_msg = f"Failed to download story from: {url}"
                log_error(error_msg, url)
                send_notification(f"Story download failed: {url}", is_error=True)
                return

            log_action(f"Downloaded: '{story_title}' by {story_author}")

            created_files = []

            if "epub" in formats:
                epub_file_name = create_epub_file(
                    story_title,
                    story_author,
                    story_content,
                    os.path.join(os.path.dirname(__file__), "data", "epubs"),
                    story_category=story_category,
                    story_tags=story_tags
                )
                created_files.append(f"EPUB: {os.path.basename(epub_file_name)}")
                log_action(f"Created EPUB: {epub_file_name}")

            if "html" in formats:
                chapter_titles = extract_chapter_titles(story_content)

                html_file_name = create_html_file(
                    story_title,
                    story_author,
                    story_content,
                    os.path.join(os.path.dirname(__file__), "data", "html"),
                    story_category=story_category,
                    story_tags=story_tags,
                    chapter_titles=chapter_titles if chapter_titles else None
                )
                created_files.append(f"HTML: {os.path.basename(html_file_name)}")
                log_action(f"Created HTML: {html_file_name}")

            formats_str = " and ".join(created_files)
            send_notification(f"Story downloaded: '{story_title}' ({formats_str})")

    except Exception as e:
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        log_error(error_msg, url)
        send_notification(f"Error processing story: {str(e)}", is_error=True)

@main.route("/api/download", methods=['GET', 'POST'])
def api_download() -> ResponseReturnValue:
    """API endpoint for iOS shortcuts to trigger downloads."""
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
        else:  # GET
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
        thread = threading.Thread(target=background_process_url, args=(app, url, validated.format))
        thread.start()
        return jsonify({
            "success": "true",
            "message": "Request accepted, processing in background"
        })
    
    return process_url(url, validated.format)

def process_url(url: str, formats: Optional[list[str]] = None) -> ResponseReturnValue:
    """Process the URL and create requested file format(s)."""
    if formats is None:
        formats = ["epub"]

    try:
        log_action(f"Starting download: {url}")
        story_content, story_title, story_author, story_category, story_tags = download_story(url)
        if not story_content:
            error_msg = f"Failed to download story from: {url}"
            log_error(error_msg, url)
            send_notification(f"Story download failed: {url}", is_error=True)
            return jsonify({
                "success": "false",
                "message": error_msg
            })

        log_action(f"Downloaded: '{story_title}' by {story_author}")

        created_files = []

        if "epub" in formats:
            epub_file_name = create_epub_file(
                story_title,
                story_author,
                story_content,
                os.path.join(os.path.dirname(__file__), "data", "epubs"),
                story_category=story_category,
                story_tags=story_tags
            )
            created_files.append(f"EPUB: {os.path.basename(epub_file_name)}")
            log_action(f"Created EPUB: {epub_file_name}")

        if "html" in formats:
            chapter_titles = extract_chapter_titles(story_content)

            html_file_name = create_html_file(
                story_title,
                story_author,
                story_content,
                os.path.join(os.path.dirname(__file__), "data", "html"),
                story_category=story_category,
                story_tags=story_tags,
                chapter_titles=chapter_titles if chapter_titles else None
            )
            created_files.append(f"HTML: {os.path.basename(html_file_name)}")
            log_action(f"Created HTML: {html_file_name}")
        
        formats_str = " and ".join(created_files)
        send_notification(f"Story downloaded: '{story_title}' ({formats_str})")

        return jsonify({
            "success": "true",
            "message": f"Successfully downloaded '{story_title}' by {story_author}",
            "title": story_title,
            "author": story_author,
            "formats": formats,
            "files": created_files
        })
    except Exception as e:
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        log_error(error_msg, url)
        send_notification(f"Error processing story: {str(e)}", is_error=True)
        return jsonify({
            "success": "false",
            "message": str(e)
        })

@main.route("/", methods=["GET", "POST"])
def index() -> ResponseReturnValue:
    if request.method == "POST":
        try:
            url = request.form.get("url", "")
            formats = request.form.getlist("format")
            if not formats:
                formats = ["epub"]

            validated = StoryDownloadRequest(url=url, wait=True, format=formats)
            return process_url(validated.url, validated.format)

        except ValidationError as e:
            error_details = e.errors()[0]
            error_msg = f"{error_details['loc'][0]}: {error_details['msg']}"
            log_error(f"Validation error on index form: {error_msg}")
            stories = get_library_data()
            categories = sorted(set(s.get('category') for s in stories if s.get('category')))
            return render_template("index.html", stories=stories, categories=categories, view='detailed', error=error_msg)

    try:
        stories = get_library_data()
        categories = sorted(set(s.get('category') for s in stories if s.get('category')))
        return render_template("index.html", stories=stories, categories=categories)
    except Exception as e:
        log_error(f"Error loading index: {str(e)}\n{traceback.format_exc()}")
        return render_template("index.html", stories=[], categories=[])

@main.route("/download/<filename>")
def download_file(filename: str) -> ResponseReturnValue:
    """Download a specific EPUB or HTML file."""
    if '..' in filename or filename.startswith('/'):
        log_error(f"Attempted path traversal in download: {filename}")
        abort(404)

    if filename.endswith('.epub'):
        output_directory = os.path.join(os.path.dirname(__file__), "data", "epubs")
    elif filename.endswith('.html'):
        output_directory = os.path.join(os.path.dirname(__file__), "data", "html")
    else:
        abort(404)

    return send_from_directory(output_directory, filename, as_attachment=True)

@main.route("/read/<filename>")
def read_story(filename: str) -> ResponseReturnValue:
    """Load story data and render with template."""
    import json
    from flask import render_template

    if '..' in filename or filename.startswith('/'):
        log_error(f"Attempted path traversal in read: {filename}")
        abort(404)

    html_directory = os.path.join(os.path.dirname(__file__), "data", "html")

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

@main.route("/sw.js")
def service_worker() -> ResponseReturnValue:
    """Serve service worker from root path to have root scope."""
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), "static"),
        "sw.js",
        mimetype='application/javascript'
    )

@main.route("/api/cover/<filename>")
def get_cover(filename: str) -> ResponseReturnValue:
    """Serve cover image for a story."""
    from .services import generate_cover_image, extract_cover_from_epub

    if '..' in filename or filename.startswith('/'):
        log_error(f"Attempted path traversal in cover request: {filename}")
        abort(404)

    if not filename.endswith('.jpg'):
        abort(404)

    cover_directory = os.path.join(os.path.dirname(__file__), "data", "covers")
    cover_path = os.path.join(cover_directory, filename)

    if os.path.exists(cover_path):
        return send_from_directory(cover_directory, filename, mimetype='image/jpeg')

    os.makedirs(cover_directory, exist_ok=True)

    sanitized_title = filename.replace('.jpg', '')
    html_directory = os.path.join(os.path.dirname(__file__), "data", "html")
    epub_directory = os.path.join(os.path.dirname(__file__), "data", "epubs")
    json_path = os.path.join(html_directory, f"{sanitized_title}.json")
    epub_path = os.path.join(epub_directory, f"{sanitized_title}.epub")

    title = sanitized_title
    author = 'Unknown Author'

    if os.path.exists(json_path):
        try:
            import json
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

def get_library_data() -> list[dict]:
    """Get library data as a list of story dictionaries."""
    import json

    epub_directory = os.path.join(os.path.dirname(__file__), "data", "epubs")
    html_directory = os.path.join(os.path.dirname(__file__), "data", "html")

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

@main.route("/api/library", methods=["GET"])
def get_library() -> ResponseReturnValue:
    """Return JSON list of all downloaded stories with metadata."""
    try:
        stories = get_library_data()
        return jsonify({"stories": stories})
    except Exception as e:
        log_error(f"Error fetching library: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"stories": []})

@main.route("/library/filter", methods=["GET"])
def filter_library() -> ResponseReturnValue:
    """Return filtered library HTML for HTMX."""
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