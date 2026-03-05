from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
from config import Config
import os
from datetime import datetime

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.analysis import analysis_bp
    from routes.admin import admin_bp
    from routes.billing import billing_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(billing_bp)

    @app.before_request
    def track_visitor():
        from models.visitor import Visitor
        if not request.path.startswith('/static'):
            try:
                v = Visitor(
                    ip_address=request.headers.get('X-Forwarded-For', request.remote_addr),
                    path=request.path[:255],
                    method=request.method,
                    user_agent=request.headers.get('User-Agent', '')[:512],
                    referrer=request.referrer[:512] if request.referrer else None,
                    session_id=''
                )
                db.session.add(v)
                db.session.commit()
            except Exception:
                db.session.rollback()

    @app.route('/health')
    def health():
        return {"status": "ok", "time": datetime.utcnow().isoformat()}

    @app.route('/home')
    def main_landing():
        from flask import redirect, url_for
        return redirect(url_for('auth.landing'))

    with app.app_context():
        db.create_all()
        # SQLite migration: add new columns if missing
        try:
            from sqlalchemy import text
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN tokens_used_this_month INTEGER DEFAULT 0"))
                conn.commit()
        except Exception:
            pass  # Column already exists
        # Bootstrap admin from env var
        admin_email = os.environ.get('BOOTSTRAP_ADMIN_EMAIL', '').strip().lower()
        if admin_email:
            try:
                from models.user import User
                u = User.query.filter_by(email=admin_email).first()
                if u and not u.is_admin:
                    u.is_admin = True
                    db.session.commit()
            except Exception:
                pass

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
