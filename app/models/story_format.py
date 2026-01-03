from __future__ import annotations
from .base import db, BaseModel, TimestampMixin

class StoryFormat(BaseModel, TimestampMixin):
    __tablename__ = 'story_formats'

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id', ondelete='CASCADE'), nullable=False, index=True)
    format_type = db.Column(db.String(10), nullable=False)

    file_path = db.Column(db.String(512), nullable=False)
    file_size = db.Column(db.Integer)
    file_hash = db.Column(db.String(64))

    json_data = db.Column(db.Text)

    story = db.relationship('Story', back_populates='formats')

    __table_args__ = (
        db.UniqueConstraint('story_id', 'format_type', name='uq_story_format'),
        db.CheckConstraint("format_type IN ('epub', 'json', 'html')", name='ck_format_type'),
    )

    def __repr__(self):
        return f'<StoryFormat {self.format_type} for story_id={self.story_id}>'
