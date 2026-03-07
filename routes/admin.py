from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from functools import wraps
from app import db
from models.user import User
from models.analysis import Analysis
from models.visitor import Visitor
from datetime import datetime, timedelta
from sqlalchemy import func

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/')
@admin_required
def dashboard():
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=6)

    total_users = User.query.count()
    active_subs = User.query.filter_by(subscription_status='active').count()
    analyses_today = Analysis.query.filter(Analysis.created_at >= today_start).count()
    total_analyses = Analysis.query.count()
    visitors_today = Visitor.query.filter(Visitor.created_at >= today_start).count()
    visitors_week = Visitor.query.filter(Visitor.created_at >= week_start).count()

    # 7-day chart data
    chart_data = []
    for i in range(6, -1, -1):
        day_start = today_start - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        count = Analysis.query.filter(
            Analysis.created_at >= day_start,
            Analysis.created_at < day_end
        ).count()
        chart_data.append({'date': day_start.strftime('%a'), 'count': count})

    recent_signups = User.query.order_by(User.created_at.desc()).limit(10).all()
    recent_analyses = Analysis.query.order_by(Analysis.created_at.desc()).limit(10).all()

    # Top pages
    top_pages = db.session.query(
        Visitor.path, func.count(Visitor.id).label('visits')
    ).group_by(Visitor.path).order_by(func.count(Visitor.id).desc()).limit(10).all()

    errors_today = Analysis.query.filter(
        Analysis.created_at >= today_start,
        Analysis.status == 'error'
    ).count()

    est_mrr = active_subs * 14.99

    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        active_subs=active_subs,
        analyses_today=analyses_today,
        total_analyses=total_analyses,
        visitors_today=visitors_today,
        visitors_week=visitors_week,
        chart_data=chart_data,
        recent_signups=recent_signups,
        recent_analyses=recent_analyses,
        top_pages=top_pages,
        est_mrr=est_mrr,
        errors_today=errors_today
    )


@admin_bp.route('/users')
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    query = User.query
    if search:
        query = query.filter(
            (User.name.ilike(f'%{search}%')) | (User.email.ilike(f'%{search}%'))
        )
    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/users.html', pagination=pagination, search=search)


@admin_bp.route('/users/new', methods=['GET', 'POST'])
@admin_required
def create_user():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        if not name or not email or not password:
            flash('Name, email, and password are required.', 'danger')
            return render_template('admin/create_user.html')
        if User.query.filter_by(email=email).first():
            flash('A user with that email already exists.', 'danger')
            return render_template('admin/create_user.html')
        user = User(
            name=name,
            email=email,
            subscription_tier=request.form.get('subscription_tier', 'free'),
            subscription_status=request.form.get('subscription_status', 'active'),
            is_admin=request.form.get('is_admin') == 'on',
            is_active_account=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash(f'User {email} created.', 'success')
        return redirect(url_for('admin.users'))
    return render_template('admin/create_user.html')


@admin_bp.route('/users/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_user(id):
    user = User.query.get_or_404(id)
    if request.method == 'POST':
        user.name = request.form.get('name', user.name).strip()
        user.email = request.form.get('email', user.email).strip().lower()
        user.backup_email = request.form.get('backup_email', '').strip().lower() or None
        user.location = request.form.get('location', '').strip()
        user.bio = request.form.get('bio', '').strip()
        user.subscription_tier = request.form.get('subscription_tier', user.subscription_tier)
        user.subscription_status = request.form.get('subscription_status', user.subscription_status)
        user.is_admin = request.form.get('is_admin') == 'on'
        user.is_active_account = request.form.get('is_active_account') == 'on'
        try:
            user.analyses_used_this_month = int(request.form.get('analyses_used_this_month', user.analyses_used_this_month or 0))
            user.tokens_used_this_month = int(request.form.get('tokens_used_this_month', user.tokens_used_this_month or 0))
        except (ValueError, TypeError):
            pass
        new_password = request.form.get('new_password', '').strip()
        if new_password:
            user.set_password(new_password)
        db.session.commit()
        flash(f'User {user.email} updated.', 'success')
        return redirect(url_for('admin.users'))
    return render_template('admin/edit_user.html', user=user)


@admin_bp.route('/users/<int:id>/delete', methods=['POST'])
@admin_required
def delete_user(id):
    user = User.query.get_or_404(id)
    db.session.delete(user)
    db.session.commit()
    flash('User deleted.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:id>/toggle-admin', methods=['POST'])
@admin_required
def toggle_admin(id):
    user = User.query.get_or_404(id)
    user.is_admin = not user.is_admin
    db.session.commit()
    flash(f'Admin status toggled for {user.email}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/analyses')
@admin_required
def analyses():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    query = Analysis.query
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    pagination = query.order_by(Analysis.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/analyses.html', pagination=pagination, status_filter=status_filter)


@admin_bp.route('/analyses/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_analysis(id):
    analysis = Analysis.query.get_or_404(id)
    if request.method == 'POST':
        analysis.status = request.form.get('status', analysis.status)
        analysis.raw_input = request.form.get('raw_input', analysis.raw_input)
        analysis.error_message = request.form.get('error_message', '')
        import json
        for field in ['extracted_product', 'price_research', 'sourcing_results', 'arbitrage_result',
                      'trend_data', 'social_data']:
            val = request.form.get(field, '')
            try:
                json.loads(val)
                setattr(analysis, field, val)
            except (ValueError, TypeError):
                if not val:
                    setattr(analysis, field, None)
                else:
                    flash(f'Invalid JSON in {field}.', 'danger')
                    return render_template('admin/edit_analysis.html', analysis=analysis)
        analysis.is_public = request.form.get('is_public') == 'on'
        db.session.commit()
        flash('Analysis updated.', 'success')
        return redirect(url_for('admin.analyses'))
    return render_template('admin/edit_analysis.html', analysis=analysis)


@admin_bp.route('/analyses/<int:id>/delete', methods=['POST'])
@admin_required
def delete_analysis(id):
    analysis = Analysis.query.get_or_404(id)
    db.session.delete(analysis)
    db.session.commit()
    flash('Analysis deleted.', 'success')
    return redirect(url_for('admin.analyses'))


@admin_bp.route('/visitors')
@admin_required
def visitors():
    page = request.args.get('page', 1, type=int)
    pagination = Visitor.query.order_by(Visitor.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    total = Visitor.query.count()
    return render_template('admin/visitors.html', pagination=pagination, total=total)


@admin_bp.route('/visitors/clear', methods=['POST'])
@admin_required
def clear_visitors():
    keep_days = request.form.get('keep_days', 'all')
    if keep_days == 'all':
        deleted = Visitor.query.delete()
    else:
        try:
            days = int(keep_days)
            cutoff = datetime.utcnow() - timedelta(days=days)
            deleted = Visitor.query.filter(Visitor.created_at < cutoff).delete()
        except (ValueError, TypeError):
            flash('Invalid option.', 'error')
            return redirect(url_for('admin.visitors'))
    db.session.commit()
    flash(f'Deleted {deleted} visitor records.', 'success')
    return redirect(url_for('admin.visitors'))
