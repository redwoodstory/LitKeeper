from __future__ import annotations
from .base import db, BaseModel

class StorySource(BaseModel):
    __tablename__ = 'story_sources'

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id', ondelete='CASCADE'), nullable=False, index=True)
    url = db.Column(db.String(512), nullable=False)
    position = db.Column(db.Integer, nullable=False)

    story = db.relationship('Story', back_populates='sources')

    def __repr__(self):
        return f'<StorySource story_id={self.story_id} pos={self.position}>'
