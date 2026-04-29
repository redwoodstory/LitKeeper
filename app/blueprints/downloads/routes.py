from __future__ import annotations
import json
import os
from flask import Blueprint, send_from_directory, abort, render_template, make_response
from flask.typing import ResponseReturnValue
from app.services import log_error
from app.utils import get_epub_directory, get_html_directory
from app.utils.security import validate_file_in_directory

downloads = Blueprint('downloads', __name__, url_prefix='/download')

@downloads.route("/html/<filename_base>")
def download_html(filename_base: str) -> ResponseReturnValue:
    if not filename_base:
        abort(404)

    # Look up the story by filename_base and get the actual JSON path from the DB,
    # because files on disk use the "{id}_{filename_base}.json" naming scheme.
    from app.models import Story, StoryFormat
    story = Story.query.filter_by(filename_base=filename_base).first()
    if not story:
        abort(404)

    json_fmt = StoryFormat.query.filter_by(story_id=story.id, format_type='json').first()
    if not json_fmt or not os.path.exists(json_fmt.file_path):
        abort(404)

    # Security: ensure resolved path stays inside the html directory
    html_dir = get_html_directory()
    if not validate_file_in_directory(html_dir, os.path.basename(json_fmt.file_path)):
        log_error(f"Path traversal blocked in html download: {filename_base}")
        abort(403)

    try:
        with open(json_fmt.file_path, 'r', encoding='utf-8') as f:
            story_data = json.load(f)
    except Exception as e:
        log_error(f"Error reading story data for html download {filename_base}: {e}")
        abort(500)

    html_content = render_template('story_export.html', story=story_data)
    response = make_response(html_content)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename_base}.html"'
    return response


@downloads.route("/<filename>")
def download_file(filename: str) -> ResponseReturnValue:
    if not filename:
        abort(404)

    if filename.endswith('.epub'):
        output_directory = get_epub_directory()
    elif filename.endswith('.html') or filename.endswith('.json'):
        output_directory = get_html_directory()
    else:
        abort(404)

    if not validate_file_in_directory(output_directory, filename):
        log_error(f"Path traversal blocked in download: {filename}")
        abort(403)

    return send_from_directory(output_directory, filename, as_attachment=True)
