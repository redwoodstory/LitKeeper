from __future__ import annotations
from flask import Blueprint, send_from_directory, abort
from flask.typing import ResponseReturnValue
from app.services import log_error
from app.utils import get_epub_directory, get_html_directory

downloads = Blueprint('downloads', __name__, url_prefix='/download')

@downloads.route("/<filename>")
def download_file(filename: str) -> ResponseReturnValue:
    if '..' in filename or filename.startswith('/'):
        log_error(f"Attempted path traversal in download: {filename}")
        abort(404)

    if filename.endswith('.epub'):
        output_directory = get_epub_directory()
    elif filename.endswith('.html'):
        output_directory = get_html_directory()
    else:
        abort(404)

    return send_from_directory(output_directory, filename, as_attachment=True)
