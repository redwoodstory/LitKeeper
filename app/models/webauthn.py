from __future__ import annotations
from datetime import datetime
from .base import db, BaseModel


class WebAuthnCredential(BaseModel):
    __tablename__ = 'webauthn_credentials'

    id            = db.Column(db.Integer, primary_key=True)
    credential_id = db.Column(db.LargeBinary, unique=True, nullable=False)
    public_key    = db.Column(db.LargeBinary, nullable=False)
    sign_count    = db.Column(db.Integer, default=0, nullable=False)
    transports    = db.Column(db.String(200))
    device_name   = db.Column(db.String(100))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
