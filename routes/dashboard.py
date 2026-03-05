from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from models.analysis import Analysis
from sqlalchemy import func

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
@login_required
def home():
    current_user.reset_monthly_if_needed()
    recent = current_user.get_recent_analyses(10)
    total_analyses = Analysis.query.filter_by(user_id=current_user.id).count()
    best_roi = 0.0
    all_analyses = Analysis.query.filter_by(user_id=current_user.id, status='complete').all()
    for a in all_analyses:
        roi = a.get_roi_value()
        if roi > best_roi:
            best_roi = roi
    return render_template(
        'dashboard/home.html',
        recent=recent,
        total_analyses=total_analyses,
        best_roi=best_roi
    )


@dashboard_bp.route('/dashboard/history')
@login_required
def history():
    page = request.args.get('page', 1, type=int)
    pagination = Analysis.query.filter_by(user_id=current_user.id).order_by(
        Analysis.created_at.desc()
    ).paginate(page=page, per_page=10, error_out=False)
    return render_template('dashboard/history.html', pagination=pagination)


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
