from __future__ import annotations
from .base import db, BaseModel, TimestampMixin
from datetime import datetime
from typing import Optional

class MetadataRefreshQueueItem(BaseModel, TimestampMixin):
    __tablename__ = 'metadata_refresh_queue'

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id', ondelete='CASCADE'), nullable=False, index=True)
    url = db.Column(db.String(512), nullable=False)
    method = db.Column(db.String(50), nullable=False, default='auto')
    status = db.Column(db.String(50), nullable=False, default='pending', index=True)
    
    progress_message = db.Column(db.String(255))
    error_message = db.Column(db.Text)
    
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    retry_count = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)
    
    story = db.relationship('Story', back_populates='metadata_refresh_jobs', foreign_keys=[story_id])

    def __repr__(self):
        return f'<MetadataRefreshQueueItem {self.id} story_id={self.story_id} {self.status}>'

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'story_id': self.story_id,
            'url': self.url,
            'method': self.method,
            'status': self.status,
            'progress_message': self.progress_message,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'retry_count': self.retry_count,
        }
