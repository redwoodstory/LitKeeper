from __future__ import annotations
from .base import db, BaseModel

class AppConfig(BaseModel):
    __tablename__ = 'app_config'

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text)
    value_type = db.Column(db.String(20), default='string')
    description = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    __table_args__ = (
        db.CheckConstraint("value_type IN ('string', 'int', 'bool', 'json')", name='ck_value_type'),
    )

    def __repr__(self):
        return f'<AppConfig {self.key}={self.value}>'

    def get_value(self):
        """Get typed value based on value_type"""
        if self.value_type == 'bool':
            return self.value.lower() == 'true'
        elif self.value_type == 'int':
            return int(self.value)
        elif self.value_type == 'json':
            import json
            return json.loads(self.value)
        return self.value

    def set_value(self, value):
        """Set value with automatic type conversion"""
        if self.value_type == 'bool':
            self.value = 'true' if value else 'false'
        elif self.value_type == 'int':
            self.value = str(value)
        elif self.value_type == 'json':
            import json
            self.value = json.dumps(value)
        else:
            self.value = str(value)
