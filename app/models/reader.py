from __future__ import annotations
from .base import db, BaseModel, TimestampMixin

class ReadingProgress(BaseModel, TimestampMixin):
    __tablename__ = 'reading_progress'

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)

    current_chapter = db.Column(db.Integer, default=1)
    current_paragraph = db.Column(db.Integer, default=0)
    scroll_position = db.Column(db.Integer, default=0)
    cfi = db.Column(db.Text)
    percentage = db.Column(db.Float)

    last_read_at = db.Column(db.DateTime, index=True)
    reading_duration_seconds = db.Column(db.Integer, default=0)
    is_completed = db.Column(db.Boolean, default=False)

    story = db.relationship('Story', back_populates='reading_progress')

    def __repr__(self):
        return f'<ReadingProgress story_id={self.story_id} chapter={self.current_chapter}>'
