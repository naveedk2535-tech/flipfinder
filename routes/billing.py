from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required
from app import csrf

billing_bp = Blueprint('billing', __name__, url_prefix='/billing')


@billing_bp.route('/pricing')
def pricing():
    return render_template('billing/plans.html')


@billing_bp.route('/create-checkout', methods=['POST'])
@login_required
def create_checkout():
    flash('All features are free during beta! Enjoy unlimited access.', 'success')
    return redirect(url_for('dashboard.home'))


@billing_bp.route('/success')
def success():
    return render_template('billing/success.html')


@billing_bp.route('/portal')
@login_required
def portal():
    flash('Billing portal coming soon. All features are free during beta!', 'info')
    return redirect(url_for('dashboard.home'))


@billing_bp.route('/webhook', methods=['POST'])
@csrf.exempt
def webhook():
    return {'status': 'ok'}, 200
