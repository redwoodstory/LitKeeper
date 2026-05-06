from __future__ import annotations
from datetime import datetime
from .base import db


class SeenLiteroticaUrl(db.Model):
    """
    Tracks every individual Literotica chapter URL that has been consumed by
    LitKeeper — whether as a standalone story or as a chapter inside a series.

    Used by the author-scan dedup check so that chapters already downloaded as
    part of a series are not re-queued when the author page is scanned again.
    """
    __tablename__ = 'seen_literotica_urls'

    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(512), unique=True, nullable=False, index=True)
    story_id = db.Column(
        db.Integer,
        db.ForeignKey('stories.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f'<SeenLiteroticaUrl {self.url!r} story_id={self.story_id}>'
