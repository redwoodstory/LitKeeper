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
    bookmarks = EpubService.get_bookmarks(story_id)
    highlights = EpubService.get_highlights(story_id)
    
    return render_template(
        'epub_reader.html',
        story=story,
        story_id=story_id,
        progress=progress,
        bookmarks=[{
            'id': b.id,
            'chapter_number': b.chapter_number,
            'paragraph_number': b.paragraph_number,
            'note': b.note,
            'created_at': b.created_at.isoformat() if b.created_at else None
        } for b in bookmarks],
        highlights=[{
            'id': h.id,
            'chapter_number': h.chapter_number,
            'paragraph_number': h.paragraph_number,
            'highlighted_text': h.highlighted_text,
            'start_offset': h.start_offset,
            'end_offset': h.end_offset,
            'note': h.note,
            'color': h.color,
            'created_at': h.created_at.isoformat() if h.created_at else None
        } for h in highlights]
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
            'cfi': None
        })

    return jsonify({
        'current_chapter': progress.current_chapter,
        'current_paragraph': progress.current_paragraph,
        'scroll_position': progress.scroll_position,
        'is_completed': progress.is_completed,
        'last_read_at': progress.last_read_at.isoformat() if progress.last_read_at else None,
        'cfi': progress.cfi
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
        cfi=data.get('cfi')
    )

    return jsonify({
        'success': True,
        'current_chapter': progress.current_chapter,
        'current_paragraph': progress.current_paragraph,
        'scroll_position': progress.scroll_position,
        'is_completed': progress.is_completed,
        'cfi': progress.cfi
    })

@epub.route('/api/bookmarks/<int:story_id>', methods=['GET'])
def get_bookmarks(story_id: int):
    """Get all bookmarks for a story."""
    story = Story.query.get_or_404(story_id)
    bookmarks = EpubService.get_bookmarks(story_id)
    
    return jsonify([{
        'id': b.id,
        'chapter_number': b.chapter_number,
        'paragraph_number': b.paragraph_number,
        'note': b.note,
        'created_at': b.created_at.isoformat() if b.created_at else None
    } for b in bookmarks])

@epub.route('/api/bookmarks/<int:story_id>', methods=['POST'])
def create_bookmark(story_id: int):
    """Create a new bookmark."""
    story = Story.query.get_or_404(story_id)
    data = request.get_json()
    
    bookmark = EpubService.create_bookmark(
        story_id=story_id,
        chapter_number=data.get('chapter_number'),
        paragraph_number=data.get('paragraph_number'),
        note=data.get('note')
    )
    
    return jsonify({
        'success': True,
        'id': bookmark.id,
        'chapter_number': bookmark.chapter_number,
        'paragraph_number': bookmark.paragraph_number,
        'note': bookmark.note,
        'created_at': bookmark.created_at.isoformat() if bookmark.created_at else None
    })

@epub.route('/api/bookmarks/<int:bookmark_id>', methods=['DELETE'])
def delete_bookmark(bookmark_id: int):
    """Delete a bookmark."""
    success = EpubService.delete_bookmark(bookmark_id)
    return jsonify({'success': success})

@epub.route('/api/highlights/<int:story_id>', methods=['GET'])
def get_highlights(story_id: int):
    """Get all highlights for a story."""
    story = Story.query.get_or_404(story_id)
    highlights = EpubService.get_highlights(story_id)
    
    return jsonify([{
        'id': h.id,
        'chapter_number': h.chapter_number,
        'paragraph_number': h.paragraph_number,
        'highlighted_text': h.highlighted_text,
        'start_offset': h.start_offset,
        'end_offset': h.end_offset,
        'note': h.note,
        'color': h.color,
        'created_at': h.created_at.isoformat() if h.created_at else None
    } for h in highlights])

@epub.route('/api/highlights/<int:story_id>', methods=['POST'])
def create_highlight(story_id: int):
    """Create a new highlight."""
    story = Story.query.get_or_404(story_id)
    data = request.get_json()
    
    highlight = EpubService.create_highlight(
        story_id=story_id,
        chapter_number=data.get('chapter_number'),
        paragraph_number=data.get('paragraph_number'),
        highlighted_text=data.get('highlighted_text'),
        start_offset=data.get('start_offset'),
        end_offset=data.get('end_offset'),
        note=data.get('note'),
        color=data.get('color', '#FFFF00')
    )
    
    return jsonify({
        'success': True,
        'id': highlight.id,
        'chapter_number': highlight.chapter_number,
        'paragraph_number': highlight.paragraph_number,
        'highlighted_text': highlight.highlighted_text,
        'start_offset': highlight.start_offset,
        'end_offset': highlight.end_offset,
        'note': highlight.note,
        'color': highlight.color,
        'created_at': highlight.created_at.isoformat() if highlight.created_at else None
    })

@epub.route('/api/highlights/<int:highlight_id>', methods=['PUT'])
def update_highlight(highlight_id: int):
    """Update a highlight."""
    data = request.get_json()
    
    highlight = EpubService.update_highlight(
        highlight_id=highlight_id,
        note=data.get('note'),
        color=data.get('color')
    )
    
    if not highlight:
        return jsonify({'success': False, 'error': 'Highlight not found'}), 404
    
    return jsonify({
        'success': True,
        'id': highlight.id,
        'note': highlight.note,
        'color': highlight.color
    })

@epub.route('/api/highlights/<int:highlight_id>', methods=['DELETE'])
def delete_highlight(highlight_id: int):
    """Delete a highlight."""
    success = EpubService.delete_highlight(highlight_id)
    return jsonify({'success': success})
