from __future__ import annotations
from .base import db, BaseModel, TimestampMixin

class ReadingProgress(BaseModel, TimestampMixin):
    __tablename__ = 'reading_progress'

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)

    current_chapter = db.Column(db.Integer, default=1)
    current_paragraph = db.Column(db.Integer, default=0)
    scroll_position = db.Column(db.Integer, default=0)

    last_read_at = db.Column(db.DateTime, index=True)
    reading_duration_seconds = db.Column(db.Integer, default=0)
    is_completed = db.Column(db.Boolean, default=False)

    story = db.relationship('Story', back_populates='reading_progress')

    def __repr__(self):
        return f'<ReadingProgress story_id={self.story_id} chapter={self.current_chapter}>'


class Bookmark(BaseModel):
    __tablename__ = 'bookmarks'

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id', ondelete='CASCADE'), nullable=False, index=True)

    chapter_number = db.Column(db.Integer, nullable=False)
    paragraph_number = db.Column(db.Integer)

    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    story = db.relationship('Story', back_populates='bookmarks')

    def __repr__(self):
        return f'<Bookmark story_id={self.story_id} chapter={self.chapter_number}>'


class Highlight(BaseModel, TimestampMixin):
    __tablename__ = 'highlights'

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id', ondelete='CASCADE'), nullable=False, index=True)

    chapter_number = db.Column(db.Integer, nullable=False)
    paragraph_number = db.Column(db.Integer, nullable=False)
    start_offset = db.Column(db.Integer)
    end_offset = db.Column(db.Integer)

    highlighted_text = db.Column(db.Text, nullable=False)
    note = db.Column(db.Text)
    color = db.Column(db.String(7), default='#FFFF00')

    story = db.relationship('Story', back_populates='highlights')

    def __repr__(self):
        return f'<Highlight story_id={self.story_id} chapter={self.chapter_number}>'
