from __future__ import annotations
from .base import db, BaseModel, TimestampMixin

class Category(BaseModel, TimestampMixin):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)

    stories = db.relationship('Story', back_populates='category', lazy='dynamic')

    def __init__(self, **kwargs):
        if 'slug' not in kwargs and 'name' in kwargs:
            kwargs['slug'] = self.create_slug(kwargs['name'])
        super().__init__(**kwargs)

    def __repr__(self):
        return f'<Category {self.name}>'

    @staticmethod
    def create_slug(name: str) -> str:
        """Create URL-friendly slug from category name"""
        return name.lower().replace(' ', '-').replace('_', '-')
