from app import db, bcrypt, login_manager
from flask_login import UserMixin
from datetime import datetime


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    avatar_url = db.Column(db.String(512), nullable=True)
    location = db.Column(db.String(255), nullable=True)
    subscription_tier = db.Column(db.String(20), default='free')
    stripe_customer_id = db.Column(db.String(255), nullable=True)
    stripe_subscription_id = db.Column(db.String(255), nullable=True)
    subscription_status = db.Column(db.String(20), default='active')
    analyses_used_this_month = db.Column(db.Integer, default=0)
    tokens_used_this_month = db.Column(db.Integer, default=0)
    is_admin = db.Column(db.Boolean, default=False)
    is_active_account = db.Column(db.Boolean, default=True)
    email_verified = db.Column(db.Boolean, default=False)
    backup_email = db.Column(db.String(255), nullable=True)
    reset_token = db.Column(db.String(255), nullable=True)
    reset_token_expires = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    last_reset_date = db.Column(db.DateTime, default=datetime.utcnow)
    subscription_trial_end = db.Column(db.DateTime, nullable=True)

    analyses = db.relationship('Analysis', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def can_analyse(self):
        # Admins and premium users always have access
        if self.is_admin or self.subscription_tier == 'premium':
            return True
        # Pro users: 50/month while subscription is active or trialing
        if self.subscription_tier == 'pro' and self.subscription_status in ('active', 'trialing'):
            return self.analyses_used_this_month < 50
        # Free tier: 3/month
        return self.analyses_used_this_month < 3

    def get_monthly_limit(self):
        if self.is_admin or self.subscription_tier == 'premium':
            return 999999
        if self.subscription_tier == 'pro':
            return 50
        return 3

    def reset_monthly_if_needed(self):
        now = datetime.utcnow()
        if self.last_reset_date is None or (
            now.year != self.last_reset_date.year or now.month != self.last_reset_date.month
        ):
            self.analyses_used_this_month = 0
            self.last_reset_date = now
            db.session.commit()

    def get_recent_analyses(self, limit=10):
        from models.analysis import Analysis
        return Analysis.query.filter_by(user_id=self.id).order_by(
            Analysis.created_at.desc()
        ).limit(limit).all()

    @property
    def is_active(self):
        return self.is_active_account

    def __repr__(self):
        return f'<User {self.email}>'
