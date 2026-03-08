from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from urllib.parse import urlparse
from app import db
from models.analysis import Analysis
from sqlalchemy import func


def _safe_redirect(next_url: str, fallback: str) -> str:
    """Return next_url only if it's a relative path on this host."""
    if next_url:
        parsed = urlparse(next_url)
        if not parsed.netloc and not parsed.scheme and next_url.startswith('/'):
            return next_url
    return fallback

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
@login_required
def home():
    current_user.reset_monthly_if_needed()
    recent = current_user.get_recent_analyses(10)
    total_analyses = Analysis.query.filter_by(user_id=current_user.id).count()

    all_complete = Analysis.query.filter_by(user_id=current_user.id, status='complete').all()
    best_roi = max((a.get_roi_value() for a in all_complete), default=0.0)

    from datetime import datetime as _dt
    now = _dt.utcnow()
    month_analyses = [
        a for a in all_complete
        if a.created_at.year == now.year and a.created_at.month == now.month
    ]
    top_flips = sorted(month_analyses, key=lambda a: a.get_roi_value(), reverse=True)[:3]
    total_profit_month = sum(
        a.get_arbitrage().get('true_net_profit', 0) for a in month_analyses
    )

    return render_template(
        'dashboard/home.html',
        recent=recent,
        total_analyses=total_analyses,
        best_roi=best_roi,
        top_flips=top_flips,
        total_profit_month=total_profit_month,
    )


@dashboard_bp.route('/dashboard/history')
@login_required
def history():
    sort = request.args.get('sort', 'date')
    cat_filter = request.args.get('cat', 'all')

    analyses = Analysis.query.filter_by(
        user_id=current_user.id
    ).order_by(Analysis.created_at.desc()).all()

    user_cats = sorted(set(a.get_category()[0] for a in analyses))

    if cat_filter != 'all':
        analyses = [a for a in analyses if a.get_category()[0] == cat_filter]

    if sort == 'roi':
        analyses.sort(key=lambda a: a.get_roi_value(), reverse=True)
    elif sort == 'profit':
        analyses.sort(key=lambda a: a.get_arbitrage().get('true_net_profit', 0), reverse=True)

    return render_template('dashboard/history.html',
        analyses=analyses, sort=sort, cat_filter=cat_filter, user_cats=user_cats)


@dashboard_bp.route('/dashboard/analysis/<int:id>/delete', methods=['POST'])
@login_required
def delete_analysis(id):
    analysis = Analysis.query.get_or_404(id)
    if analysis.user_id != current_user.id:
        flash('Access denied.', 'danger')
    else:
        db.session.delete(analysis)
        db.session.commit()
    next_url = _safe_redirect(request.form.get('next'), url_for('dashboard.home'))
    return redirect(next_url)


@dashboard_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        location = request.form.get('location', '').strip()
        bio = request.form.get('bio', '').strip()[:500]
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if len(name) < 2:
            flash('Name must be at least 2 characters.', 'danger')
            return render_template('profile.html')

        current_user.name = name
        current_user.location = location
        current_user.bio = bio

        if new_password:
            if len(new_password) < 8:
                flash('New password must be at least 8 characters.', 'danger')
                return render_template('profile.html')
            if new_password != confirm_password:
                flash('Passwords do not match.', 'danger')
                return render_template('profile.html')
            current_user.set_password(new_password)

        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('dashboard.profile'))

    return render_template('profile.html')
