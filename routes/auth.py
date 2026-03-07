from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from urllib.parse import urlparse, urljoin
from app import db, mail, limiter
from models.user import User
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)


def _is_safe_url(target):
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in ('http', 'https') and ref.netloc == test.netloc

# ── Token helpers ─────────────────────────────────────────────────────────────

def _serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

def _send_verification_email(user):
    token = _serializer().dumps(user.email, salt='email-verify')
    link  = url_for('auth.verify_email', token=token, _external=True)
    msg   = Message('Verify your FlipAFind account', recipients=[user.email])
    msg.body = (
        f"Hi {user.name},\n\n"
        f"Please verify your FlipAFind account by clicking (or copying) the link below:\n\n"
        f"{link}\n\n"
        f"This link expires in 24 hours.\n"
        f"If you didn't sign up, ignore this email.\n\n"
        f"— FlipAFind"
    )
    msg.html = f"""
    <div style="font-family:sans-serif;background:#09090f;color:#f1f5f9;padding:32px;">
      <div style="max-width:480px;margin:auto;background:#1a1a28;border:1px solid #252532;
                  border-radius:16px;padding:32px;">
        <h2 style="color:#a5b4fc;margin:0 0 8px;">Confirm your email</h2>
        <p style="color:#94a3b8;margin:0 0 20px;">
          Hi {user.name}, click the link below to verify your email and activate your FlipAFind account.
        </p>
        <p style="margin:0 0 8px;">
          <a href="{link}" style="color:#818cf8;word-break:break-all;">{link}</a>
        </p>
        <p style="color:#52526a;font-size:12px;margin-top:24px;">
          Link expires in 24 hours. If you didn't sign up, ignore this email.
        </p>
      </div>
    </div>
    """
    mail.send(msg)

def _send_reset_email(user, token, recipients=None):
    link = url_for('auth.reset_password', token=token, _external=True)
    if recipients is None:
        recipients = [user.email]
    msg  = Message('Reset your FlipAFind password', recipients=recipients)
    msg.body = (
        f"Hi {user.name},\n\n"
        f"Click (or copy) the link below to reset your FlipAFind password:\n\n"
        f"{link}\n\n"
        f"This link expires in 1 hour.\n"
        f"If you didn't request this, ignore this email — your password won't change.\n\n"
        f"— FlipAFind"
    )
    msg.html = f"""
    <div style="font-family:sans-serif;background:#09090f;color:#f1f5f9;padding:32px;">
      <div style="max-width:480px;margin:auto;background:#1a1a28;border:1px solid #252532;
                  border-radius:16px;padding:32px;">
        <h2 style="color:#a5b4fc;margin:0 0 8px;">Reset your password</h2>
        <p style="color:#94a3b8;margin:0 0 20px;">
          Hi {user.name}, click the link below to set a new password. Expires in 1 hour.
        </p>
        <p style="margin:0 0 8px;">
          <a href="{link}" style="color:#818cf8;word-break:break-all;">{link}</a>
        </p>
        <p style="color:#52526a;font-size:12px;margin-top:24px;">
          If you didn't request this, ignore this email — your password won't change.
        </p>
      </div>
    </div>
    """
    mail.send(msg)


# ── Routes ────────────────────────────────────────────────────────────────────

@auth_bp.route('/')
def landing():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
    return render_template('landing.html')


@auth_bp.route('/signup', methods=['GET', 'POST'])
@limiter.limit("10 per hour", methods=["POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        terms    = request.form.get('terms')
        plan     = request.form.get('plan', 'free')
        if plan not in ('free', 'pro', 'premium'):
            plan = 'free'

        if len(name) < 2:
            flash('Name must be at least 2 characters.', 'danger')
            return render_template('auth/signup.html', selected_plan=plan)
        if '@' not in email or '.' not in email:
            flash('Please enter a valid email address.', 'danger')
            return render_template('auth/signup.html', selected_plan=plan)
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('auth/signup.html', selected_plan=plan)
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/signup.html', selected_plan=plan)
        if not terms:
            flash('You must accept the terms and conditions.', 'danger')
            return render_template('auth/signup.html', selected_plan=plan)
        if User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'danger')
            return render_template('auth/signup.html', selected_plan=plan)

        user = User(
            name=name,
            email=email,
            email_verified=False,
            subscription_tier='free',
            subscription_status='active'
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Store chosen paid plan in session — applied after email verification
        if plan in ('pro', 'premium'):
            session['signup_plan'] = plan

        try:
            _send_verification_email(user)
        except Exception as e:
            current_app.logger.error(f"Verification email failed: {e}")

        return render_template('auth/verify_pending.html', email=email, chosen_plan=plan)

    return render_template('auth/signup.html', selected_plan='free')


@auth_bp.route('/verify/<token>')
def verify_email(token):
    try:
        email = _serializer().loads(token, salt='email-verify', max_age=86400)
    except SignatureExpired:
        flash('Verification link has expired. Request a new one below.', 'danger')
        return render_template('auth/verify_pending.html', expired=True)
    except BadSignature:
        flash('Invalid verification link.', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Account not found.', 'danger')
        return redirect(url_for('auth.login'))

    user.email_verified = True
    db.session.commit()
    login_user(user)

    # If they chose a paid plan at signup, send them to pricing to complete checkout
    signup_plan = session.pop('signup_plan', None)
    if signup_plan in ('pro', 'premium'):
        flash(f'Email verified! Now start your 10-day free trial to activate your {signup_plan.capitalize()} plan.', 'success')
        return redirect(url_for('billing.pricing'))

    flash(f'Email verified! Welcome to FlipAFind, {user.name}!', 'success')
    return redirect(url_for('dashboard.home'))


@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    email = request.form.get('email', '').strip().lower()
    user  = User.query.filter_by(email=email).first()
    if user and not user.email_verified:
        try:
            _send_verification_email(user)
        except Exception as e:
            current_app.logger.error(f"Resend verification failed: {e}")
    flash('If that email is registered and unverified, a new link has been sent.', 'info')
    return render_template('auth/verify_pending.html', email=email)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per 15 minutes", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password   = request.form.get('password', '')
        user = User.query.filter(User.name.ilike(identifier)).first()
        if not user:
            user = User.query.filter_by(email=identifier.lower()).first()

        if user and user.check_password(password) and user.is_active_account:
            if not user.email_verified:
                return render_template('auth/verify_pending.html',
                                       email=user.email, unverified=True)
            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user)
            flash(f'Welcome back, {user.name}!', 'success')
            next_page = request.args.get('next')
            if next_page and not _is_safe_url(next_page):
                next_page = None
            return redirect(next_page or url_for('dashboard.home'))
        flash('Invalid username or password.', 'danger')
    return render_template('auth/login.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("5 per hour", methods=["POST"])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user  = User.query.filter_by(email=email).first()
        if not user:
            user = User.query.filter_by(backup_email=email).first()
        if user:
            token = _serializer().dumps(user.email, salt='password-reset')
            user.reset_token         = token
            user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            recipients = [user.email]
            if user.backup_email and user.backup_email not in recipients:
                recipients.append(user.backup_email)
            try:
                _send_reset_email(user, token, recipients)
            except Exception as e:
                current_app.logger.error(f"Reset email failed: {e}")
        flash('If an account with that email exists, a reset link has been sent.', 'info')
        return render_template('auth/forgot_password.html', sent=True)
    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = _serializer().loads(token, salt='password-reset', max_age=3600)
    except (SignatureExpired, BadSignature):
        flash('Password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    user = User.query.filter_by(email=email).first()
    if not user or user.reset_token != token:
        flash('Invalid reset link.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('auth/reset_password.html', token=token)
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html', token=token)
        user.set_password(password)
        user.reset_token         = None
        user.reset_token_expires = None
        user.email_verified      = True
        db.session.commit()
        login_user(user)
        flash('Password reset successfully. Welcome back!', 'success')
        return redirect(url_for('dashboard.home'))

    return render_template('auth/reset_password.html', token=token)


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.landing'))


@auth_bp.route('/privacy')
def privacy():
    return render_template('privacy.html')


@auth_bp.route('/terms')
def terms():
    return render_template('terms.html')
