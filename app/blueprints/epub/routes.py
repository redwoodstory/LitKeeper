from __future__ import annotations
import os
from flask import jsonify, request, abort, send_from_directory
from . import epub
from app.models import Story, ReadingProgress, StoryFormat
from app.services.epub_service import EpubService
from app.utils import get_epub_directory
from datetime import datetime

@epub.route('/api/progress/bulk', methods=['GET'])
def get_progress_bulk():
    ids_param = request.args.get('ids', '')
    if not ids_param:
        return jsonify({'progress': {}})
    try:
        story_ids = [int(i) for i in ids_param.split(',') if i.strip()]
    except ValueError:
        return jsonify({'error': 'Invalid ids parameter'}), 400

    records = ReadingProgress.query.filter(ReadingProgress.story_id.in_(story_ids)).all()
    progress_map = {r.story_id: r for r in records}

    result = {}
    for story_id in story_ids:
        p = progress_map.get(story_id)
        if p:
            result[str(story_id)] = {
                'current_chapter': p.current_chapter,
                'current_paragraph': p.current_paragraph,
                'scroll_position': p.scroll_position,
                'is_completed': p.is_completed,
                'last_read_at': p.last_read_at.isoformat() if p.last_read_at else None,
                'cfi': p.cfi,
                'paragraph_id': p.paragraph_id,
                'percentage': p.percentage
            }
        else:
            result[str(story_id)] = {
                'current_chapter': 1,
                'current_paragraph': 0,
                'scroll_position': 0,
                'is_completed': False,
                'last_read_at': None,
                'cfi': None,
                'paragraph_id': None,
                'percentage': None
            }

    return jsonify({'progress': result})


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
            'paragraph_id': None,
            'percentage': None
        })

    return jsonify({
        'current_chapter': progress.current_chapter,
        'current_paragraph': progress.current_paragraph,
        'scroll_position': progress.scroll_position,
        'is_completed': progress.is_completed,
        'last_read_at': progress.last_read_at.isoformat() if progress.last_read_at else None,
        'cfi': progress.cfi,
        'paragraph_id': progress.paragraph_id,
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
        paragraph_id=data.get('paragraph_id'),
        percentage=data.get('percentage')
    )

    return jsonify({
        'success': True,
        'current_chapter': progress.current_chapter,
        'current_paragraph': progress.current_paragraph,
        'scroll_position': progress.scroll_position,
        'is_completed': progress.is_completed,
        'cfi': progress.cfi,
        'paragraph_id': progress.paragraph_id,
        'percentage': progress.percentage
    })

@epub.route('/api/progress/<int:story_id>', methods=['DELETE'])
def reset_progress(story_id: int):
    """Reset reading progress for a story."""
    from app.models import db
    Story.query.get_or_404(story_id)
    progress = ReadingProgress.query.filter_by(story_id=story_id).first()
    if progress:
        db.session.delete(progress)
        db.session.commit()
    return jsonify({'success': True})


@epub.route('/file/<int:story_id>', methods=['GET'])
def serve_epub_file(story_id: int):
    """Serve EPUB file for a story and track last_opened_at."""
    from app.models import db
    
    story = Story.query.get_or_404(story_id)
    
    # Update last_opened_at timestamp
    story.last_opened_at = datetime.utcnow()
    db.session.commit()
    
    epub_format = StoryFormat.query.filter_by(story_id=story_id, format_type='epub').first()
    if not epub_format or not os.path.exists(epub_format.file_path):
        abort(404)

    epub_directory = os.path.dirname(epub_format.file_path)
    epub_filename = os.path.basename(epub_format.file_path)
    return send_from_directory(epub_directory, epub_filename, as_attachment=False, mimetype='application/epub+zip')
