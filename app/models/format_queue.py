from __future__ import annotations
from .base import db, BaseModel, TimestampMixin
from datetime import datetime


class FormatQueueItem(BaseModel, TimestampMixin):
    """Tracks async format-generation jobs (HTML/EPUB) so they run in a background thread."""
    __tablename__ = 'format_queue'

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id', ondelete='CASCADE'), nullable=False, index=True)
    # generate_epub | generate_html | generate_html_with_metadata
    job_type = db.Column(db.String(50), nullable=False)
    # Only populated for generate_html_with_metadata
    url = db.Column(db.String(512))
    method = db.Column(db.String(50), default='manual')
    status = db.Column(db.String(50), nullable=False, default='pending', index=True)

    progress_message = db.Column(db.String(255))
    error_message = db.Column(db.Text)

    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'story_id': self.story_id,
            'job_type': self.job_type,
            'url': self.url,
            'status': self.status,
            'progress_message': self.progress_message,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }
