from flask import Blueprint, request, render_template, send_from_directory, jsonify, abort, current_app
from .utils import download_story, create_epub_file, log_error, log_action, log_url, send_telegram_message
import os
from datetime import datetime
import traceback
import urllib.parse
from threading import Thread

# Blueprint for module routing
main = Blueprint('main', __name__)

def background_process_url(app, url):
    """Process URL in background without returning JSON response."""
    try:
        with app.app_context():
            # Download the story and generate the EPUB
            log_action("Starting story download")
            story_content, story_title, story_author, story_category, story_tags = download_story(url)
            if not story_content:
                error_msg = f"Failed to download the story from the given URL: {url}"
                log_error(error_msg, url)
                log_action(f"Download failed: {error_msg}")
                send_telegram_message(f"Story download failed: {url}", is_error=True)
                return

            log_action(f"Successfully downloaded story: '{story_title}' by {story_author}")
            log_action("Starting EPUB creation")

            epub_file_name = create_epub_file(
                story_title, 
                story_author, 
                story_content, 
                os.path.join(os.path.dirname(__file__), "data", "epubs"),
                story_category=story_category,
                story_tags=story_tags
            )
            log_action(f"Successfully created EPUB file: {epub_file_name}")
            send_telegram_message(f"Story downloaded successfully: '{story_title}' by {story_author}")

    except Exception as e:
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        log_error(error_msg, url)
        log_action(f"Error occurred: {str(e)}")
        send_telegram_message(f"Error processing story: {str(e)}", is_error=True)

@main.route("/api/download", methods=['GET', 'POST'])
def api_download():
    """API endpoint for iOS shortcuts to trigger downloads."""
    # Log request details for debugging
    log_action(f"API Request Method: {request.method}")
    log_action(f"Request Headers: {dict(request.headers)}")
    
    if request.method == 'POST':
        log_action(f"POST Raw Data: {request.get_data(as_text=True)}")
        
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
            url = data.get('url')
            wait = data.get('wait', True)
            if isinstance(wait, str):
                wait = wait.lower() == 'true'
        else:
            log_action(f"POST Form Data: {dict(request.form)}")
            url = request.form.get('url')
            wait = request.form.get('wait', 'true').lower() == 'true'
    else:  # GET
        log_action(f"GET Query Parameters: {dict(request.args)}")
        url = request.args.get('url')
        wait = request.args.get('wait', 'true').lower() == 'true'

    if not url:
        error_msg = "API request received without URL parameter"
        log_error(f"{error_msg}\nRequest Method: {request.method}\nHeaders: {dict(request.headers)}\nData: {request.get_data(as_text=True)}")
        return jsonify({
            "success": "false",
            "message": error_msg
        }), 400

    # Clean the URL: remove whitespace, newlines, and decode
    url = url.strip()  # Remove leading/trailing whitespace
    url = url.split()[0]  # Take only the first URL if multiple are provided
    url = urllib.parse.unquote(url)  # URL decode
    
    log_action(f"API request received for URL: {url}")
    
    # Log URL once at the entry point
    log_url(url)
    
    # Check if URL is from allowed domain
    if not url.startswith("https://www.literotica.com/"):
        error_msg = f"Invalid URL domain: {url}"
        log_error(error_msg, url)
        return jsonify({
            "success": "false",
            "message": error_msg
        }), 400

    if not wait:
        # Get the current app context
        app = current_app._get_current_object()
        # Start processing in background thread
        thread = Thread(target=background_process_url, args=(app, url))
        thread.start()
        return jsonify({
            "success": "true",
            "message": "Request accepted, processing in background"
        })

    return process_url(url)

def process_url(url):
    """Process the URL and create EPUB file."""
    try:
        # Download the story and generate the EPUB
        log_action("Starting story download")
        story_content, story_title, story_author, story_category, story_tags = download_story(url)
        if not story_content:
            error_msg = f"Failed to download the story from the given URL: {url}"
            log_error(error_msg, url)
            log_action(f"Download failed: {error_msg}")
            send_telegram_message(f"Story download failed: {url}", is_error=True)
            return jsonify({
                "success": "false",
                "message": error_msg
            })

        log_action(f"Successfully downloaded story: '{story_title}' by {story_author}")
        log_action("Starting EPUB creation")

        epub_file_name = create_epub_file(
            story_title, 
            story_author, 
            story_content, 
            os.path.join(os.path.dirname(__file__), "data", "epubs"),
            story_category=story_category,
            story_tags=story_tags
        )
        log_action(f"Successfully created EPUB file: {epub_file_name}")
        send_telegram_message(f"Story downloaded successfully: '{story_title}' by {story_author}")

        # Get the base filename without path
        base_filename = os.path.basename(epub_file_name)

        return jsonify({
            "success": "true",
            "message": f"Successfully downloaded '{story_title}' by {story_author}",
            "title": story_title,
            "author": story_author,
            "saved_as": base_filename
        })
    except Exception as e:
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        log_error(error_msg, url)
        log_action(f"Error occurred: {str(e)}")
        send_telegram_message(f"Error processing story: {str(e)}", is_error=True)
        return jsonify({
            "success": "false",
            "message": str(e)
        })

@main.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form.get("url")
        return process_url(url)

    log_action("Serving index page")
    return render_template("index.html")

@main.route("/download/<filename>")
def download_file(filename):
    """Download a specific EPUB file."""
    # Basic security check: ensure filename doesn't contain path traversal
    if '..' in filename or filename.startswith('/'):
        log_action(f"Attempted path traversal in download: {filename}")
        abort(404)
        
    output_directory = os.path.join(os.path.dirname(__file__), "data", "epubs")
    log_action(f"Download requested for file: {filename}")
    return send_from_directory(output_directory, filename, as_attachment=True)