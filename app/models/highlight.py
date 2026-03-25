from __future__ import annotations
from .base import db, BaseModel, TimestampMixin


class Highlight(BaseModel, TimestampMixin):
    __tablename__ = 'highlights'

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id', ondelete='CASCADE'), nullable=False, index=True)
    chapter_index = db.Column(db.Integer, nullable=False)
    paragraph_index = db.Column(db.Integer, nullable=False)
    quote_text = db.Column(db.Text, nullable=False)
    note = db.Column(db.Text, nullable=True)

    story = db.relationship('Story', back_populates='highlights')

    def __repr__(self):
        return f'<Highlight story_id={self.story_id} ch={self.chapter_index} para={self.paragraph_index}>'
