from __future__ import annotations
from flask import render_template, jsonify, request, send_file, abort, current_app
from . import epub
from app.models import Story
from app.services.epub_service import EpubService
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
    
    try:
        with zipfile.ZipFile(epub_path, 'r') as zip_file:
            # Try to read the requested file from the EPUB
            try:
                file_data = zip_file.read(filepath)
            except KeyError:
                abort(404, description=f"File {filepath} not found in EPUB")
            
            # Determine MIME type based on file extension
            mimetype = 'application/octet-stream'
            if filepath.endswith('.xml'):
                mimetype = 'application/xml'
            elif filepath.endswith('.xhtml') or filepath.endswith('.html'):
                mimetype = 'application/xhtml+xml'
            elif filepath.endswith('.css'):
                mimetype = 'text/css'
            elif filepath.endswith('.js'):
                mimetype = 'application/javascript'
            elif filepath.endswith('.jpg') or filepath.endswith('.jpeg'):
                mimetype = 'image/jpeg'
            elif filepath.endswith('.png'):
                mimetype = 'image/png'
            elif filepath.endswith('.gif'):
                mimetype = 'image/gif'
            elif filepath.endswith('.svg'):
                mimetype = 'image/svg+xml'
            elif filepath.endswith('.opf'):
                mimetype = 'application/oebps-package+xml'
            elif filepath.endswith('.ncx'):
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
