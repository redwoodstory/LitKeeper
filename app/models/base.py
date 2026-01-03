from __future__ import annotations
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from typing import Any

db = SQLAlchemy()

class TimestampMixin:
    """Mixin for created_at/updated_at timestamps"""
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class BaseModel(db.Model):
    """Base model with common functionality"""
    __abstract__ = True

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary"""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    def update(self, **kwargs):
        """Update model attributes"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
