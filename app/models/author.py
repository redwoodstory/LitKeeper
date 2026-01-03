from __future__ import annotations
from .base import db, BaseModel, TimestampMixin

class Author(BaseModel, TimestampMixin):
    __tablename__ = 'authors'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False, index=True)
    literotica_url = db.Column(db.String(512), unique=True, index=True)

    stories = db.relationship('Story', back_populates='author', lazy='dynamic')

    def __repr__(self):
        return f'<Author {self.name}>'
