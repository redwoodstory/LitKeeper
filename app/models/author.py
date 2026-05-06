from __future__ import annotations
import json
from datetime import datetime
from typing import Optional
from .base import db, BaseModel, TimestampMixin

class Author(BaseModel, TimestampMixin):
    __tablename__ = 'authors'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False, index=True)
    literotica_url = db.Column(db.String(512), unique=True, index=True)

    watch_enabled = db.Column(db.Boolean, nullable=False, default=False)
    last_watch_check_at = db.Column(db.DateTime, nullable=True)
    known_story_urls = db.Column(db.Text, nullable=True)

    stories = db.relationship('Story', back_populates='author', lazy='dynamic')

    def __repr__(self):
        return f'<Author {self.name}>'

    def get_known_story_urls(self) -> list[str]:
        if not self.known_story_urls:
            return []
        try:
            return json.loads(self.known_story_urls)
        except Exception:
            return []

    def set_known_story_urls(self, urls: list[str]) -> None:
        self.known_story_urls = json.dumps(urls) if urls else None

    def to_dict(self) -> dict:
        story_count = self.stories.count()
        return {
            'id': self.id,
            'name': self.name,
            'literotica_url': self.literotica_url,
            'watch_enabled': self.watch_enabled,
            'last_watch_check_at': self.last_watch_check_at.isoformat() if self.last_watch_check_at else None,
            'story_count': story_count,
            'known_story_count': len(self.get_known_story_urls()),
        }
