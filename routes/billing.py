import os
import logging
import stripe
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import csrf, db
from models.user import User

logger = logging.getLogger(__name__)

billing_bp = Blueprint('billing', __name__, url_prefix='/billing')

PLAN_PRICE_IDS = {
    'pro':     os.environ.get('STRIPE_PRO_PRICE_ID', ''),
    'premium': os.environ.get('STRIPE_PREMIUM_PRICE_ID', ''),
}


def _stripe():
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')
    return stripe


@billing_bp.route('/pricing')
def pricing():
    return render_template('billing/plans.html',
                           stripe_pk=os.environ.get('STRIPE_PUBLISHABLE_KEY', ''))


@billing_bp.route('/create-checkout', methods=['POST'])
@login_required
def create_checkout():
    # Admins always have full access — no need to subscribe
    if current_user.is_admin:
        flash('Admin accounts have full access to all features.', 'info')
        return redirect(url_for('dashboard.home'))

    plan = request.form.get('plan', 'pro')
    price_id = PLAN_PRICE_IDS.get(plan)
    if not price_id:
        flash('Invalid plan selected.', 'danger')
        return redirect(url_for('billing.pricing'))

    s = _stripe()
    try:
        # Get or create Stripe customer
        customer_id = current_user.stripe_customer_id
        if not customer_id:
            customer = s.Customer.create(
                email=current_user.email,
                name=current_user.name,
                metadata={'user_id': current_user.id}
            )
            customer_id = customer.id
            current_user.stripe_customer_id = customer_id
            db.session.commit()

        session = s.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription',
            subscription_data={
                'trial_period_days': 10,
                'metadata': {'user_id': str(current_user.id), 'plan': plan},
            },
            allow_promotion_codes=True,
            success_url=url_for('billing.success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('billing.pricing', _external=True),
            metadata={'user_id': str(current_user.id), 'plan': plan},
        )
        return redirect(session.url, code=303)

    except Exception as e:
        logger.error(f'Stripe checkout error: {e}')
        flash('Could not start checkout. Please try again.', 'danger')
        return redirect(url_for('billing.pricing'))


@billing_bp.route('/success')
@login_required
def success():
    return render_template('billing/success.html',
                           session_id=request.args.get('session_id'))


@billing_bp.route('/portal')
@login_required
def portal():
    if not current_user.stripe_customer_id:
        flash('No active subscription found. Please subscribe first.', 'warning')
        return redirect(url_for('billing.pricing'))

    s = _stripe()
    try:
        session = s.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=url_for('dashboard.home', _external=True),
        )
        return redirect(session.url, code=303)
    except Exception as e:
        logger.error(f'Stripe portal error: {e}')
        flash('Could not open billing portal. Please try again.', 'danger')
        return redirect(url_for('dashboard.home'))


# ── Webhook ──────────────────────────────────────────────────────────────────

@billing_bp.route('/webhook', methods=['POST'])
@csrf.exempt
def webhook():
    payload = request.get_data()
    sig = request.headers.get('Stripe-Signature', '')
    secret = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

    s = _stripe()
    try:
        event = s.Webhook.construct_event(payload, sig, secret)
    except stripe.error.SignatureVerificationError as e:
        logger.warning(f'Webhook signature invalid: {e}')
        return jsonify({'error': 'Invalid signature'}), 400
    except Exception as e:
        logger.error(f'Webhook parse error: {e}')
        return jsonify({'error': str(e)}), 400

    _dispatch(event)
    return jsonify({'status': 'ok'})


def _dispatch(event):
    handlers = {
        'checkout.session.completed':    _on_checkout_completed,
        'customer.subscription.updated': _on_subscription_updated,
        'customer.subscription.deleted': _on_subscription_deleted,
    }
    handler = handlers.get(event['type'])
    if handler:
        try:
            handler(event['data']['object'])
        except Exception as e:
            logger.error(f"Error in handler for {event['type']}: {e}")


def _user_by_customer(customer_id):
    return User.query.filter_by(stripe_customer_id=customer_id).first()


def _on_checkout_completed(session):
    user_id = (session.get('metadata') or {}).get('user_id')
    plan    = (session.get('metadata') or {}).get('plan', 'pro')
    cust_id = session.get('customer')

    user = User.query.get(int(user_id)) if user_id else _user_by_customer(cust_id)
    if not user:
        logger.warning(f'checkout.session.completed: no user for id={user_id}')
        return

    user.stripe_customer_id     = cust_id
    user.stripe_subscription_id = session.get('subscription')
    user.subscription_tier      = plan
    # Stripe marks the session status 'trialing' when a trial is active
    user.subscription_status    = 'trialing' if session.get('status') == 'trialing' else 'active'
    db.session.commit()
    logger.info(f'Checkout complete: {user.email} → {plan} ({user.subscription_status})')


def _on_subscription_updated(sub):
    user = _user_by_customer(sub['customer'])
    if not user:
        return

    status = sub.get('status', '')
    if status in ('active', 'trialing'):
        user.subscription_status = status
        items = sub.get('items', {}).get('data', [])
        if items:
            price_id = items[0].get('price', {}).get('id', '')
            if price_id == os.environ.get('STRIPE_PREMIUM_PRICE_ID', ''):
                user.subscription_tier = 'premium'
            elif price_id == os.environ.get('STRIPE_PRO_PRICE_ID', ''):
                user.subscription_tier = 'pro'
    elif status in ('canceled', 'unpaid', 'past_due'):
        user.subscription_status = status
        if status == 'canceled':
            user.subscription_tier = 'free'

    db.session.commit()
    logger.info(f'Subscription updated: {user.email} → {status}')


def _on_subscription_deleted(sub):
    user = _user_by_customer(sub['customer'])
    if not user:
        return
    user.subscription_tier      = 'free'
    user.subscription_status    = 'canceled'
    user.stripe_subscription_id = None
    db.session.commit()
    logger.info(f'Subscription deleted: {user.email}')
