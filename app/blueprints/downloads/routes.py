from __future__ import annotations
from flask import Blueprint, send_from_directory, abort
from flask.typing import ResponseReturnValue
from app.services import log_error
from app.utils import get_epub_directory, get_html_directory
from app.utils.security import validate_file_in_directory

downloads = Blueprint('downloads', __name__, url_prefix='/download')

@downloads.route("/<filename>")
def download_file(filename: str) -> ResponseReturnValue:
    if not filename:
        abort(404)

    if filename.endswith('.epub'):
        output_directory = get_epub_directory()
    elif filename.endswith('.html'):
        output_directory = get_html_directory()
    else:
        abort(404)

    if not validate_file_in_directory(output_directory, filename):
        log_error(f"Path traversal blocked in download: {filename}")
        abort(403)

    return send_from_directory(output_directory, filename, as_attachment=True)
