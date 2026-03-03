from __future__ import annotations
from .base import db, BaseModel, TimestampMixin
from datetime import datetime
from typing import Optional
import json

class DownloadQueueItem(BaseModel, TimestampMixin):
    __tablename__ = 'download_queue'

    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(512), nullable=False, index=True)
    formats = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='pending', index=True)

    title = db.Column(db.String(500))
    author = db.Column(db.String(255))
    category = db.Column(db.String(100))
    tags = db.Column(db.Text)

    story_id = db.Column(db.Integer, db.ForeignKey('stories.id', ondelete='SET NULL'), index=True)

    total_pages = db.Column(db.Integer)
    downloaded_pages = db.Column(db.Integer, default=0)
    file_size = db.Column(db.Integer)

    progress_message = db.Column(db.String(255))
    error_message = db.Column(db.Text)

    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    retry_count = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)

    def __repr__(self):
        return f'<DownloadQueueItem {self.id} {self.url} {self.status}>'

    def get_formats(self) -> list[str]:
        """Parse formats from JSON string"""
        try:
            return json.loads(self.formats)
        except:
            return ['epub', 'html']

    def set_formats(self, formats: list[str]) -> None:
        """Store formats as JSON string"""
        self.formats = json.dumps(formats)

    def get_tags(self) -> Optional[list[str]]:
        """Parse tags from JSON string"""
        if not self.tags:
            return None
        try:
            return json.loads(self.tags)
        except:
            return None

    def set_tags(self, tags: Optional[list[str]]) -> None:
        """Store tags as JSON string"""
        if tags:
            self.tags = json.dumps(tags)
        else:
            self.tags = None

    def get_queue_position(self) -> int:
        """Get position in queue (1-indexed)"""
        if self.status not in ['pending', 'processing']:
            return 0
        
        earlier_items = DownloadQueueItem.query.filter(
            DownloadQueueItem.status.in_(['pending', 'processing']),
            DownloadQueueItem.created_at < self.created_at
        ).count()
        
        return earlier_items + 1

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'url': self.url,
            'formats': self.get_formats(),
            'status': self.status,
            'title': self.title,
            'author': self.author,
            'category': self.category,
            'tags': self.get_tags(),
            'story_id': self.story_id,
            'total_pages': self.total_pages,
            'downloaded_pages': self.downloaded_pages,
            'file_size': self.file_size,
            'progress_message': self.progress_message,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'retry_count': self.retry_count,
            'queue_position': self.get_queue_position(),
        }
