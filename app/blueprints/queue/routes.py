from __future__ import annotations
from flask import Blueprint, render_template, jsonify
from flask.typing import ResponseReturnValue
from app.models import DownloadQueueItem, db
from app.services import log_error
from sqlalchemy import desc

queue = Blueprint('queue', __name__, url_prefix='/queue')

@queue.route('/')
def index() -> ResponseReturnValue:
    pending_items = DownloadQueueItem.query.filter_by(status='pending').order_by(DownloadQueueItem.created_at.asc()).all()
    processing_items = DownloadQueueItem.query.filter_by(status='processing').order_by(DownloadQueueItem.started_at.desc()).all()
    completed_items = DownloadQueueItem.query.filter_by(status='completed').order_by(desc(DownloadQueueItem.completed_at)).limit(50).all()
    failed_items = DownloadQueueItem.query.filter_by(status='failed').order_by(desc(DownloadQueueItem.completed_at)).limit(20).all()

    pending_with_position = []
    for idx, item in enumerate(pending_items, start=1):
        item_dict = item.to_dict()
        item_dict['queue_position'] = idx
        pending_with_position.append(item_dict)

    return render_template('queue/index.html',
                           pending=len(pending_items),
                           processing=len(processing_items),
                           completed=DownloadQueueItem.query.filter_by(status='completed').count(),
                           failed=DownloadQueueItem.query.filter_by(status='failed').count(),
                           queue_pending=pending_with_position,
                           queue_processing=[i.to_dict() for i in processing_items],
                           queue_completed=[i.to_dict() for i in completed_items],
                           queue_failed=[i.to_dict() for i in failed_items])

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
            'failed': DownloadQueueItem.query.filter_by(status='failed').count()
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
            'failed': DownloadQueueItem.query.filter_by(status='failed').count()
        }
        return render_template('queue/partials/stats.html', **stats)
    except Exception as e:
        log_error(f"Error rendering queue stats: {str(e)}")
        return '<div class="text-red-600 dark:text-red-400">Error loading stats</div>', 500

@queue.route('/partials/list')
def queue_list_partial() -> ResponseReturnValue:
    """HTMX partial for queue list"""
    try:
        pending = DownloadQueueItem.query.filter_by(status='pending').order_by(DownloadQueueItem.created_at.asc()).all()
        processing = DownloadQueueItem.query.filter_by(status='processing').order_by(DownloadQueueItem.started_at.desc()).all()
        completed = DownloadQueueItem.query.filter_by(status='completed').order_by(desc(DownloadQueueItem.completed_at)).limit(50).all()
        failed = DownloadQueueItem.query.filter_by(status='failed').order_by(desc(DownloadQueueItem.completed_at)).limit(20).all()

        pending_with_position = []
        for idx, item in enumerate(pending, start=1):
            item_dict = item.to_dict()
            item_dict['queue_position'] = idx
            pending_with_position.append(item_dict)

        return render_template('queue/partials/queue_list.html',
                             pending=pending_with_position,
                             processing=[item.to_dict() for item in processing],
                             completed=[item.to_dict() for item in completed],
                             failed=[item.to_dict() for item in failed])
    except Exception as e:
        log_error(f"Error rendering queue list: {str(e)}")
        return '<div class="text-red-600 dark:text-red-400">Error loading queue</div>', 500
