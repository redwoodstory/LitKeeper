from __future__ import annotations
import io
import json
import os
import re
import zipfile
from flask import Blueprint, send_file, send_from_directory, abort, render_template, make_response
from flask.typing import ResponseReturnValue
from app.services import log_error
from app.utils import get_epub_directory, get_html_directory
from app.utils.security import validate_file_in_directory

downloads = Blueprint('downloads', __name__, url_prefix='/download')


def _friendly_epub_filename(story) -> str:
    """Build a human-readable epub filename from story metadata."""
    category = story.category.name if story.category else None
    author = story.author.name if story.author else 'Unknown'
    title = story.title

    parts = [p for p in [category, author, title] if p]
    name = ' - '.join(parts)
    # Strip characters that are invalid in filenames across common OSes
    name = re.sub(r'[/\\:*?"<>|]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return f'{name}.epub'


@downloads.route("/export/epub/<int:story_id>")
def export_epub(story_id: int) -> ResponseReturnValue:
    from app.models import Story, StoryFormat
    story = Story.query.get(story_id)
    if not story:
        abort(404)

    epub_fmt = StoryFormat.query.filter_by(story_id=story.id, format_type='epub').first()
    if not epub_fmt or not os.path.exists(epub_fmt.file_path):
        abort(404)

    epub_dir = get_epub_directory()
    filename_on_disk = os.path.basename(epub_fmt.file_path)
    if not validate_file_in_directory(epub_dir, filename_on_disk):
        log_error(f"Path traversal blocked in epub export: story_id={story_id}")
        abort(403)

    friendly_name = _friendly_epub_filename(story)
    return send_file(
        epub_fmt.file_path,
        as_attachment=True,
        download_name=friendly_name,
        mimetype='application/epub+zip',
    )


@downloads.route("/export/all")
def export_all_epubs() -> ResponseReturnValue:
    from app.models import Story
    epub_dir = get_epub_directory()

    stories = Story.query.all()

    buf = io.BytesIO()
    seen_names: dict[str, int] = {}

    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for story in stories:
            epub_fmt = next((f for f in story.formats if f.format_type == 'epub'), None)
            if not epub_fmt or not epub_fmt.file_path or not os.path.exists(epub_fmt.file_path):
                continue
            if not validate_file_in_directory(epub_dir, os.path.basename(epub_fmt.file_path)):
                continue

            name = _friendly_epub_filename(story)
            # Deduplicate names within the zip
            if name in seen_names:
                seen_names[name] += 1
                base, ext = name.rsplit('.', 1)
                name = f'{base} ({seen_names[name]}).{ext}'
            else:
                seen_names[name] = 0

            # Read bytes first so Python can write a complete local header without
            # a trailing data descriptor record, which Archive Utility rejects.
            with open(epub_fmt.file_path, 'rb') as f:
                zf.writestr(name, f.read())

    data = buf.getvalue()
    response = make_response(data)
    response.headers['Content-Type'] = 'application/zip'
    response.headers['Content-Disposition'] = 'attachment; filename="litkeeper-library.zip"'
    response.headers['Content-Length'] = str(len(data))
    return response


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
