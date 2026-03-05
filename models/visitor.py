from app import db
from datetime import datetime


class Visitor(db.Model):
    __tablename__ = 'visitors'

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(64))
    path = db.Column(db.String(255))
    method = db.Column(db.String(10))
    user_agent = db.Column(db.String(512))
    referrer = db.Column(db.String(512), nullable=True)
    session_id = db.Column(db.String(64), nullable=True)
    country = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<Visitor {self.ip_address} {self.path}>'
