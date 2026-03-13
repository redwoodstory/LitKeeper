from __future__ import annotations
from .base import db, BaseModel, TimestampMixin
from typing import Optional

class Story(BaseModel, TimestampMixin):
    __tablename__ = 'stories'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('authors.id', ondelete='RESTRICT'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='SET NULL'), index=True)

    literotica_url = db.Column(db.String(512), unique=True, index=True)
    literotica_series_url = db.Column(db.String(512), index=True)
    literotica_page_count = db.Column(db.Integer)

    word_count = db.Column(db.Integer)
    chapter_count = db.Column(db.Integer, default=1)

    filename_base = db.Column(db.String(255), unique=True, nullable=False, index=True)
    cover_filename = db.Column(db.String(255))

    imported_at = db.Column(db.DateTime)
    last_metadata_refresh = db.Column(db.DateTime)
    metadata_refresh_status = db.Column(db.String(50), default='never')

    auto_update_enabled = db.Column(db.Boolean, default=True, nullable=False)
    last_update_check_at = db.Column(db.DateTime)
    content_hash = db.Column(db.String(64))
    
    auto_refresh_excluded = db.Column(db.Boolean, default=False, nullable=False)
    auto_refresh_exclusion_reason = db.Column(db.String(500))
    auto_refresh_exclusion_type = db.Column(db.String(50))

    rating = db.Column(db.Integer, nullable=True)
    in_queue = db.Column(db.Boolean, default=False, nullable=False)

    author = db.relationship('Author', back_populates='stories', lazy='joined')
    category = db.relationship('Category', back_populates='stories', lazy='joined')
    tags = db.relationship('Tag', secondary='story_tags', back_populates='stories', lazy='subquery')
    formats = db.relationship('StoryFormat', back_populates='story', cascade='all, delete-orphan', lazy='subquery')
    reading_progress = db.relationship('ReadingProgress', back_populates='story', uselist=False, cascade='all, delete-orphan')
    metadata_refresh_jobs = db.relationship('MetadataRefreshQueueItem', back_populates='story', cascade='all, delete-orphan', lazy='dynamic')

    def __repr__(self):
        return f'<Story {self.title}>'

    def set_tags(self, tag_names: list[str]) -> None:
        """Update story tags from a list of tag names"""
        from .tag import Tag
        
        tag_objects = []
        for tag_name in tag_names:
            if not tag_name or not tag_name.strip():
                continue
            
            tag_name = tag_name.strip()
            tag = Tag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                db.session.add(tag)
                db.session.flush()
            tag_objects.append(tag)
        
        self.tags = tag_objects

    def to_library_dict(self) -> dict:
        """Convert to library display format (backward compatible with current UI)"""
        epub_format = next((f for f in self.formats if f.format_type == 'epub'), None)
        html_format = next((f for f in self.formats if f.format_type in ('html', 'json')), None)

        return {
            'id': self.id,
            'title': self.title,
            'author': self.author.name if self.author else 'Unknown',
            'author_url': self.author.literotica_url if self.author and self.author.literotica_url else None,
            'category': self.category.name if self.category else None,
            'tags': [tag.name for tag in self.tags],
            'cover': self.cover_filename,
            'filename_base': self.filename_base,
            'formats': [fmt.format_type for fmt in self.formats],
            'epub_file': f"{self.filename_base}.epub" if epub_format else None,
            'html_file': f"{self.filename_base}.html" if html_format else None,
            'source_url': self.literotica_url,
            'page_count': self.literotica_page_count,
            'word_count': self.word_count,
            'size': epub_format.file_size if epub_format else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'auto_update_enabled': self.auto_update_enabled,
            'series_url': self.literotica_series_url,
            'is_series': bool(self.literotica_series_url and self.chapter_count > 1),
            'rating': self.rating,
            'in_queue': bool(self.in_queue),
        }
