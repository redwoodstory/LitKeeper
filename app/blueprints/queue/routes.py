from __future__ import annotations
from flask import Blueprint, render_template, jsonify
from flask.typing import ResponseReturnValue
from app.models import DownloadQueueItem, db
from app.services import log_error
from app.services.logger import log_action
from sqlalchemy import desc, and_, not_

queue = Blueprint('queue', __name__, url_prefix='/queue')

def _visible_items_query():
    """Items shown in the queue list — excludes skipped duplicates and completed author scans."""
    return DownloadQueueItem.query.filter(
        DownloadQueueItem.status != 'skipped',
        not_(and_(
            DownloadQueueItem.job_type == 'author',
            DownloadQueueItem.status == 'completed'
        ))
    )


@queue.route('/')
def index() -> ResponseReturnValue:
    all_items = _visible_items_query().order_by(desc(DownloadQueueItem.created_at)).limit(70).all()

    rate_limited_count = DownloadQueueItem.query.filter_by(status='rate_limited').count()
    return render_template('queue/index.html',
                           pending=DownloadQueueItem.query.filter_by(status='pending').count(),
                           processing=DownloadQueueItem.query.filter_by(status='processing').count(),
                           completed=DownloadQueueItem.query.filter_by(status='completed').count(),
                           failed=DownloadQueueItem.query.filter_by(status='failed').count(),
                           rate_limited=rate_limited_count,
                           queue_items=[i.to_dict() for i in all_items])

@queue.route('/api/items')
def get_queue_items() -> ResponseReturnValue:
    """Get all queue items grouped by status"""
    try:
        pending = DownloadQueueItem.query.filter_by(status='pending').order_by(DownloadQueueItem.created_at.asc()).all()
        processing = DownloadQueueItem.query.filter_by(status='processing').order_by(DownloadQueueItem.started_at.desc()).all()
        completed = DownloadQueueItem.query.filter_by(status='completed').order_by(desc(DownloadQueueItem.completed_at)).limit(50).all()
        failed = DownloadQueueItem.query.filter_by(status='failed').order_by(desc(DownloadQueueItem.completed_at)).limit(20).all()

        return jsonify({
            'pending': [item.to_dict() for item in pending],
            'processing': [item.to_dict() for item in processing],
            'completed': [item.to_dict() for item in completed],
            'failed': [item.to_dict() for item in failed]
        })
    except Exception as e:
        log_error(f"Error fetching queue items: {str(e)}")
        return jsonify({'error': 'Failed to fetch queue items'}), 500

@queue.route('/api/items/<int:item_id>')
def get_queue_item(item_id: int) -> ResponseReturnValue:
    """Get a single queue item by ID"""
    try:
        item = db.session.get(DownloadQueueItem, item_id)
        if not item:
            return jsonify({'error': 'Item not found'}), 404
        return jsonify(item.to_dict())
    except Exception as e:
        log_error(f"Error fetching queue item {item_id}: {str(e)}")
        return jsonify({'error': 'Failed to fetch queue item'}), 500

@queue.route('/api/stats')
def get_queue_stats() -> ResponseReturnValue:
    """Get queue statistics"""
    try:
        stats = {
            'pending': DownloadQueueItem.query.filter_by(status='pending').count(),
            'processing': DownloadQueueItem.query.filter_by(status='processing').count(),
            'completed': DownloadQueueItem.query.filter_by(status='completed').count(),
            'failed': DownloadQueueItem.query.filter_by(status='failed').count(),
            'rate_limited': DownloadQueueItem.query.filter_by(status='rate_limited').count(),
        }
        return jsonify(stats)
    except Exception as e:
        log_error(f"Error fetching queue stats: {str(e)}")
        return jsonify({'error': 'Failed to fetch stats'}), 500

@queue.route('/partials/stats')
def queue_stats_partial() -> ResponseReturnValue:
    """HTMX partial for queue stats"""
    try:
        stats = {
            'pending': DownloadQueueItem.query.filter_by(status='pending').count(),
            'processing': DownloadQueueItem.query.filter_by(status='processing').count(),
            'completed': DownloadQueueItem.query.filter_by(status='completed').count(),
            'failed': DownloadQueueItem.query.filter_by(status='failed').count(),
            'rate_limited': DownloadQueueItem.query.filter_by(status='rate_limited').count(),
        }
        return render_template('queue/partials/stats.html', **stats)
    except Exception as e:
        log_error(f"Error rendering queue stats: {str(e)}")
        return '<div class="text-red-600 dark:text-red-400">Error loading stats</div>', 500

@queue.route('/partials/list')
def queue_list_partial() -> ResponseReturnValue:
    """HTMX partial for queue list"""
    try:
        all_items = _visible_items_query().order_by(desc(DownloadQueueItem.created_at)).limit(70).all()
        return render_template('queue/partials/queue_list.html',
                               items=[item.to_dict() for item in all_items])
    except Exception as e:
        log_error(f"Error rendering queue list: {str(e)}")
        return '<div class="text-red-600 dark:text-red-400">Error loading queue</div>', 500


@queue.route('/api/items/<int:item_id>', methods=['DELETE'])
def cancel_queue_item(item_id: int) -> ResponseReturnValue:
    """Cancel or remove a single queue item."""
    try:
        item = db.session.get(DownloadQueueItem, item_id)
        if not item:
            return jsonify({'success': False, 'message': 'Item not found'}), 404

        label = item.title or item.url
        if item.status == 'processing':
            item.status = 'failed'
            item.error_message = 'Cancelled by user'
            db.session.commit()
            log_action(f"[Queue] Cancelled processing item {item_id}: {label}")
        else:
            db.session.delete(item)
            db.session.commit()
            log_action(f"[Queue] Removed queue item {item_id}: {label}")

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        log_error(f"Error cancelling queue item {item_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to cancel item'}), 500


@queue.route('/api/clear', methods=['DELETE'])
def clear_history() -> ResponseReturnValue:
    """Delete all completed and failed queue items."""
    try:
        deleted = DownloadQueueItem.query.filter(
            DownloadQueueItem.status.in_(['completed', 'failed', 'skipped'])
        ).delete(synchronize_session=False)
        db.session.commit()
        log_action(f"[Queue] Cleared {deleted} completed/failed history items")
        return jsonify({'success': True, 'deleted': deleted})
    except Exception as e:
        db.session.rollback()
        log_error(f"Error clearing queue history: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to clear history'}), 500
