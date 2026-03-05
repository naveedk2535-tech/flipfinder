from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from models.user import User
from datetime import datetime

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def landing():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
    return render_template('landing.html')


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        terms = request.form.get('terms')

        if len(name) < 2:
            flash('Name must be at least 2 characters.', 'danger')
            return render_template('auth/signup.html')
        if '@' not in email or '.' not in email:
            flash('Please enter a valid email address.', 'danger')
            return render_template('auth/signup.html')
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('auth/signup.html')
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/signup.html')
        if not terms:
            flash('You must accept the terms and conditions.', 'danger')
            return render_template('auth/signup.html')
        if User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'danger')
            return render_template('auth/signup.html')

        user = User(
            name=name,
            email=email,
            subscription_tier='premium',
            subscription_status='active'
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash(f'Welcome to FlipFinder, {name}! You have full access during beta.', 'success')
        return redirect(url_for('dashboard.home'))

    return render_template('auth/signup.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.is_active_account:
            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user)
            flash(f'Welcome back, {user.name}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.home'))
        flash('Invalid email or password.', 'danger')
    return render_template('auth/login.html')


@auth_bp.route('/logout')
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
