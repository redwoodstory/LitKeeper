from __future__ import annotations
from flask import render_template, jsonify, request, send_file, abort, current_app
from . import epub
from app.models import Story
from app.services.epub_service import EpubService
from app.utils.security import sanitize_zip_path
from app.services.logger import log_error
import os

@epub.route('/reader/<int:story_id>')
def reader(story_id: int):
    """Render the EPUB reader page."""
    story = Story.query.get_or_404(story_id)
    
    epub_path = EpubService.get_epub_path(story)
    if not epub_path:
        abort(404, description="EPUB file not found for this story")
    
    progress = EpubService.get_reading_progress(story_id)

    return render_template(
        'epub_reader.html',
        story=story,
        story_id=story_id,
        progress=progress
    )

@epub.route('/file/<int:story_id>')
def serve_epub(story_id: int):
    """Serve the EPUB file for reading."""
    story = Story.query.get_or_404(story_id)
    
    epub_path = EpubService.get_epub_path(story)
    if not epub_path or not os.path.exists(epub_path):
        abort(404, description="EPUB file not found")
    
    return send_file(
        epub_path,
        mimetype='application/epub+zip',
        as_attachment=False,
        download_name=f"{story.filename_base}.epub"
    )

@epub.route('/file/<int:story_id>/<path:filepath>')
def serve_epub_resource(story_id: int, filepath: str):
    """Serve individual files from within the EPUB archive."""
    import zipfile
    from io import BytesIO

    story = Story.query.get_or_404(story_id)
    epub_path = EpubService.get_epub_path(story)

    if not epub_path or not os.path.exists(epub_path):
        abort(404, description="EPUB file not found")

    safe_filepath = sanitize_zip_path(filepath)
    if not safe_filepath:
        log_error(f"Path traversal blocked: story={story_id}, path={filepath}")
        abort(403, description="Invalid file path")

    try:
        with zipfile.ZipFile(epub_path, 'r') as zip_file:
            if safe_filepath not in zip_file.namelist():
                abort(404, description="File not found in EPUB")

            try:
                file_data = zip_file.read(safe_filepath)
            except KeyError:
                abort(404, description=f"File {safe_filepath} not found in EPUB")
            
            # Determine MIME type based on file extension
            mimetype = 'application/octet-stream'
            if safe_filepath.endswith('.xml'):
                mimetype = 'application/xml'
            elif safe_filepath.endswith('.xhtml') or safe_filepath.endswith('.html'):
                mimetype = 'application/xhtml+xml'
            elif safe_filepath.endswith('.css'):
                mimetype = 'text/css'
            elif safe_filepath.endswith('.js'):
                mimetype = 'application/javascript'
            elif safe_filepath.endswith('.jpg') or safe_filepath.endswith('.jpeg'):
                mimetype = 'image/jpeg'
            elif safe_filepath.endswith('.png'):
                mimetype = 'image/png'
            elif safe_filepath.endswith('.gif'):
                mimetype = 'image/gif'
            elif safe_filepath.endswith('.svg'):
                mimetype = 'image/svg+xml'
            elif safe_filepath.endswith('.opf'):
                mimetype = 'application/oebps-package+xml'
            elif safe_filepath.endswith('.ncx'):
                mimetype = 'application/x-dtbncx+xml'
            
            return send_file(
                BytesIO(file_data),
                mimetype=mimetype,
                as_attachment=False
            )
    except zipfile.BadZipFile:
        abort(500, description="Invalid EPUB file")

@epub.route('/api/progress/<int:story_id>', methods=['GET'])
def get_progress(story_id: int):
    """Get reading progress for a story."""
    story = Story.query.get_or_404(story_id)
    progress = EpubService.get_reading_progress(story_id)

    if not progress:
        return jsonify({
            'current_chapter': 1,
            'current_paragraph': 0,
            'scroll_position': 0,
            'is_completed': False,
            'last_read_at': None,
            'cfi': None,
            'percentage': None
        })

    return jsonify({
        'current_chapter': progress.current_chapter,
        'current_paragraph': progress.current_paragraph,
        'scroll_position': progress.scroll_position,
        'is_completed': progress.is_completed,
        'last_read_at': progress.last_read_at.isoformat() if progress.last_read_at else None,
        'cfi': progress.cfi,
        'percentage': progress.percentage
    })

@epub.route('/api/progress/<int:story_id>', methods=['POST'])
def update_progress(story_id: int):
    """Update reading progress for a story."""
    story = Story.query.get_or_404(story_id)
    data = request.get_json()

    progress = EpubService.update_reading_progress(
        story_id=story_id,
        current_chapter=data.get('current_chapter'),
        current_paragraph=data.get('current_paragraph'),
        scroll_position=data.get('scroll_position'),
        is_completed=data.get('is_completed'),
        cfi=data.get('cfi'),
        percentage=data.get('percentage')
    )

    return jsonify({
        'success': True,
        'current_chapter': progress.current_chapter,
        'current_paragraph': progress.current_paragraph,
        'scroll_position': progress.scroll_position,
        'is_completed': progress.is_completed,
        'cfi': progress.cfi,
        'percentage': progress.percentage
    })
