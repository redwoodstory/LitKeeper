#!/usr/bin/env python3
"""
One-time script to reset stuck metadata refresh queue items.
Run this with: docker exec litkeeper-test python3 reset_stuck_queue.py
"""
from app import create_app
from app.models import MetadataRefreshQueueItem, Story, db

app = create_app()

with app.app_context():
    stuck_items = MetadataRefreshQueueItem.query.filter(
        MetadataRefreshQueueItem.status == 'processing'
    ).all()
    
    if stuck_items:
        print(f"Found {len(stuck_items)} stuck items in 'processing' status")
        for item in stuck_items:
            story = db.session.get(Story, item.story_id)
            print(f"  - Item {item.id}: {story.title if story else 'Unknown'} (retry: {item.retry_count})")
            item.status = 'pending'
            item.started_at = None
            item.progress_message = 'Reset from stuck processing state'
        
        db.session.commit()
        print(f"\nReset {len(stuck_items)} items to 'pending' status")
    else:
        print("No stuck items found")
    
    pending = MetadataRefreshQueueItem.query.filter_by(status='pending').count()
    processing = MetadataRefreshQueueItem.query.filter_by(status='processing').count()
    completed = MetadataRefreshQueueItem.query.filter_by(status='completed').count()
    failed = MetadataRefreshQueueItem.query.filter_by(status='failed').count()
    
    print(f"\nQueue status:")
    print(f"  Pending: {pending}")
    print(f"  Processing: {processing}")
    print(f"  Completed: {completed}")
    print(f"  Failed: {failed}")
