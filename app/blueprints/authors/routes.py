from __future__ import annotations
from flask import render_template, request, jsonify, current_app
from flask.typing import ResponseReturnValue
from . import authors_bp
from app.models import Author, db
from app.services.logger import log_action, log_error
from sqlalchemy import func
import traceback


@authors_bp.route('/')
def index() -> ResponseReturnValue:
    authors = Author.query.filter(
        Author.literotica_url.isnot(None)
    ).order_by(func.lower(Author.name)).all()
    return render_template('authors/index.html', authors=authors)


@authors_bp.route('/rescan/<int:author_id>', methods=['POST'])
def rescan_author(author_id: int) -> ResponseReturnValue:
    """Manually trigger a re-scan of an author's story list."""
    try:
        author = db.session.get(Author, author_id)
        if not author or not author.literotica_url:
            return jsonify({"success": False, "message": "Author not found"}), 404

        from app.models import DownloadQueueItem
        import json

        existing = DownloadQueueItem.query.filter(
            DownloadQueueItem.url == author.literotica_url,
            DownloadQueueItem.status.in_(['pending', 'processing'])
        ).first()
        if existing:
            return jsonify({"success": True, "message": "Scan already queued"})

        queue_item = DownloadQueueItem(
            url=author.literotica_url,
            formats=json.dumps(['epub', 'html']),
            status='pending',
            job_type='author',
            author=author.name,
            title=f'Author scan: {author.name}',
        )
        db.session.add(queue_item)
        db.session.commit()
        current_app.download_worker.wake()
        log_action(f"Manual rescan queued for author '{author.name}'")
        return jsonify({"success": True, "message": f"Rescan queued for {author.name}"})

    except Exception as e:
        log_error(f"Error queuing author rescan: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"success": False, "message": "Internal server error"}), 500
