from flask import Flask, request, jsonify, redirect, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    _limiter_available = True
except ImportError:
    _limiter_available = False
from config import Config
import os
from datetime import datetime

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
csrf = CSRFProtect()
mail = Mail()

if _limiter_available:
    limiter = Limiter(key_func=get_remote_address, default_limits=[])
else:
    import logging
    logging.getLogger(__name__).warning("flask-limiter not installed — rate limiting disabled")
    class _NoOpLimiter:
        def init_app(self, app): pass
        def limit(self, *a, **kw):
            def decorator(f): return f
            return decorator
    limiter = _NoOpLimiter()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Mail config
    app.config['MAIL_SERVER']         = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT']           = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS']        = True
    app.config['MAIL_USERNAME']       = os.environ.get('MAIL_USERNAME', 'hello@zzi.ai')
    app.config['MAIL_PASSWORD']       = os.environ.get('MAIL_PASSWORD', '')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'FlipAFind <hello@zzi.ai>')

    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)

    # ── Security headers ────────────────────────────────────────────────────
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # Prevent browsers caching HTML pages so updates show immediately on refresh
        if 'text/html' in response.content_type:
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    # ── HTTPS redirect (PythonAnywhere proxy sets X-Forwarded-Proto) ────────
    @app.before_request
    def redirect_to_https():
        proto = request.headers.get('X-Forwarded-Proto', 'https')
        if proto == 'http' and not app.debug:
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url, code=301)

    # ── Error handlers ───────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    @app.errorhandler(429)
    def ratelimit_handler(e):
        from flask import request as req, flash as fls, redirect as redir, url_for as ufl
        fls('Too many attempts. Please wait and try again.', 'danger')
        return redir(req.referrer or ufl('auth.landing'))

    # ── robots.txt ───────────────────────────────────────────────────────────
    @app.route('/robots.txt')
    def robots():
        from flask import Response
        txt = (
            "User-agent: *\n"
            "Allow: /\n"
            "Disallow: /admin/\n"
            "Disallow: /dashboard/\n"
            "Disallow: /billing/webhook\n"
            f"Sitemap: https://www.flipafind.com/sitemap.xml\n"
        )
        return Response(txt, mimetype='text/plain')

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.analysis import analysis_bp
    from routes.admin import admin_bp
    from routes.billing import billing_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(api_bp)
    csrf.exempt(api_bp)

    # IPs to exclude from visitor log (admin traffic)
    EXCLUDED_IPS = {'96.227.109.218'}

    @app.before_request
    def track_visitor():
        from models.visitor import Visitor
        if not request.path.startswith('/static'):
            ip = request.headers.get('X-Forwarded-For', request.remote_addr) or ''
            # X-Forwarded-For can be comma-separated; take the first (client) IP
            client_ip = ip.split(',')[0].strip()
            if client_ip in EXCLUDED_IPS:
                return
            try:
                v = Visitor(
                    ip_address=client_ip,
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
        from sqlalchemy import text
        _migrations = [
            "ALTER TABLE users ADD COLUMN tokens_used_this_month INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN email_verified INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN reset_token TEXT",
            "ALTER TABLE users ADD COLUMN reset_token_expires DATETIME",
            "ALTER TABLE analyses ADD COLUMN trend_data TEXT",
            "ALTER TABLE analyses ADD COLUMN social_data TEXT",
            "ALTER TABLE analyses ADD COLUMN is_public INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN backup_email VARCHAR(255)",
            "ALTER TABLE users ADD COLUMN subscription_trial_end DATETIME",
        ]
        with db.engine.connect() as conn:
            for sql in _migrations:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                except Exception:
                    pass  # Column already exists

        # Mark all existing users as verified so they aren't locked out
        try:
            with db.engine.connect() as conn:
                conn.execute(text("UPDATE users SET email_verified = 1 WHERE email_verified IS NULL OR email_verified = 0"))
                conn.commit()
        except Exception:
            pass
        # Bootstrap admin from env var (upsert: create if missing, update if exists)
        admin_email = os.environ.get('BOOTSTRAP_ADMIN_EMAIL', '').strip().lower()
        admin_pw    = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD', '').strip()
        if admin_email:
            try:
                from models.user import User
                u = User.query.filter_by(email=admin_email).first()
                if not u:
                    u = User(
                        name='Admin',
                        email=admin_email,
                        email_verified=True,
                        is_admin=True,
                        is_active_account=True,
                        subscription_tier='premium',
                        subscription_status='active',
                    )
                    u.set_password(admin_pw or 'changeme123')
                    db.session.add(u)
                else:
                    u.is_admin = True
                    u.is_active_account = True
                    u.email_verified = True
                    if admin_pw:
                        u.set_password(admin_pw)
                db.session.commit()
            except Exception:
                pass

        # Seed default accounts (admin2 + tester) — only created once, never overwritten
        try:
            from models.user import User
            _seed = [
                dict(name='Admin 2', email='admin2@flipafind.com',   password='FlipAdmin2!',   is_admin=True,  tier='premium'),
                dict(name='Tester',  email='tester@flipafind.com',   password='FlipTest123!',  is_admin=False, tier='premium'),
            ]
            for s in _seed:
                if not User.query.filter_by(email=s['email']).first():
                    nu = User(
                        name=s['name'], email=s['email'],
                        email_verified=True, is_active_account=True,
                        is_admin=s['is_admin'],
                        subscription_tier=s['tier'],
                        subscription_status='active',
                    )
                    nu.set_password(s['password'])
                    db.session.add(nu)
            db.session.commit()
        except Exception:
            pass

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
