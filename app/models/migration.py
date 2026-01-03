from __future__ import annotations
from .base import db, BaseModel

class MigrationLog(BaseModel):
    __tablename__ = 'migration_log'

    id = db.Column(db.Integer, primary_key=True)
    migration_session_id = db.Column(db.String(36), nullable=False, index=True)

    file_path = db.Column(db.String(512), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)

    status = db.Column(db.String(20), nullable=False, index=True)
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id', ondelete='SET NULL'))
    error_message = db.Column(db.Text)

    processed_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    __table_args__ = (
        db.CheckConstraint("status IN ('success', 'failed', 'skipped', 'duplicate')", name='ck_migration_status'),
    )

    def __repr__(self):
        return f'<MigrationLog {self.file_path} - {self.status}>'

    def to_dict(self):
        return {
            'id': self.id,
            'migration_session_id': self.migration_session_id,
            'file_path': self.file_path,
            'file_type': self.file_type,
            'status': self.status,
            'story_id': self.story_id,
            'error_message': self.error_message,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None
        }


class MetadataRefreshLog(BaseModel):
    __tablename__ = 'metadata_refresh_log'

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id', ondelete='CASCADE'), nullable=False, index=True)

    search_query = db.Column(db.String(512))

    status = db.Column(db.String(20), nullable=False)
    matched_url = db.Column(db.String(512))
    match_confidence = db.Column(db.Numeric(3, 2))

    metadata_updated = db.Column(db.Boolean, default=False)
    fields_changed = db.Column(db.Text)

    error_message = db.Column(db.Text)
    refreshed_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    __table_args__ = (
        db.CheckConstraint("status IN ('success', 'failed', 'no_match', 'user_skipped', 'manual_link')", name='ck_refresh_status'),
    )

    def __repr__(self):
        return f'<MetadataRefreshLog story_id={self.story_id} - {self.status}>'
