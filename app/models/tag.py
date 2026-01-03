from __future__ import annotations
from .base import db, BaseModel, TimestampMixin

story_tags = db.Table('story_tags',
    db.Column('story_id', db.Integer, db.ForeignKey('stories.id', ondelete='CASCADE'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True),
    db.Column('created_at', db.DateTime, default=db.func.current_timestamp())
)

class Tag(BaseModel, TimestampMixin):
    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)

    stories = db.relationship('Story', secondary=story_tags, back_populates='tags', lazy='dynamic')

    def __repr__(self):
        return f'<Tag {self.name}>'

    @staticmethod
    def create_slug(name: str) -> str:
        """Create URL-friendly slug from tag name"""
        return name.lower().replace(' ', '-').replace('_', '-')
