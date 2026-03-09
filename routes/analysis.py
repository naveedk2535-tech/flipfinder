import os
import uuid
import base64
import json
import io
from datetime import datetime, timedelta
from threading import Thread
from PIL import Image as PilImage
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app import db, limiter
from models.analysis import Analysis
from agents.extraction_agent import extract_product_details
from agents.pricing_agent import research_prices
from agents.sourcing_agent import find_sourcing_deals
from agents.arbitrage_agent import calculate_arbitrage
from agents.trends_agent import get_trend_data, get_social_data
from utils.currency import convert_to_usd

analysis_bp = Blueprint('analysis', __name__, url_prefix='/analyse')


def allowed_file(filename):
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'jpg', 'jpeg', 'png', 'webp'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def _run_analysis_bg(app, analysis_id, user_id, image_base64, image_media_type,
                     text_input, link_input, has_text, has_link):
    with app.app_context():
        analysis = Analysis.query.get(analysis_id)
        if not analysis:
            return
        try:
            # Agent 1: Extract product details
            extracted = extract_product_details(
                text_input=text_input if has_text else None,
                image_base64=image_base64,
                image_media_type=image_media_type,
                link=link_input if has_link else None
            )
            analysis.extracted_product = json.dumps(extracted)
            db.session.commit()

            search_query = extracted.get('search_query', text_input or 'product')
            # For image inputs the AI over-specifies (color, size, condition) making searches too narrow.
            # Simplify to brand + product_type + model only.
            if image_base64:
                parts = [
                    extracted.get('brand', ''),
                    extracted.get('product_type', ''),
                    extracted.get('model', ''),
                ]
                simple_query = ' '.join(p for p in parts if p and p.lower() not in ('unknown', '')).strip()
                if simple_query:
                    search_query = simple_query

            # Currency conversion: if listing price is in a foreign currency, convert to USD
            listing_currency = (extracted.get('listing_currency') or 'USD').upper()
            raw_listing_price = float(extracted.get('listing_price', 0) or 0)
            if listing_currency != 'USD' and raw_listing_price > 0:
                converted_price, conv_method = convert_to_usd(raw_listing_price, listing_currency)
                extracted['listing_price_original'] = raw_listing_price
                extracted['listing_price_original_currency'] = listing_currency
                extracted['listing_price'] = converted_price
                extracted['currency_conversion_method'] = conv_method
                # Re-save extracted with converted price
                analysis.extracted_product = json.dumps(extracted)
                db.session.commit()

            # When a URL was submitted, the listing price on that page IS the buy price.
            # Pass it through so the sourcing agent anchors cheapest_found to the real price.
            input_price = float(extracted.get('listing_price', 0) or 0) if has_link else 0

            # Agent 2: Pricing first (sourcing needs avg_sold to compute target buy price)
            pricing = research_prices(search_query, extracted)
            analysis.price_research = json.dumps(pricing)
            db.session.commit()

            # Agent 3: Sourcing with real avg_sold data
            avg_sold = pricing.get('avg_sold', 0) or 0
            sourcing = find_sourcing_deals(search_query, avg_sold, extracted, input_price)

            # Cross-validation: detect buy/sell spread anomalies
            cheapest = sourcing.get('cheapest_found', 0) or 0
            if avg_sold > 0 and cheapest > 0:
                spread_pct = (avg_sold - cheapest) / avg_sold
                if cheapest > avg_sold:
                    sourcing['market_spread_warning'] = (
                        f"WARNING: Cheapest available (${cheapest:.0f}) exceeds median sold (${avg_sold:.0f}). "
                        f"The market may be cooling or listings are overpriced. Wait for a price drop."
                    )
                elif spread_pct < 0.10:
                    sourcing['market_spread_warning'] = (
                        f"Tight market: cheapest listing (${cheapest:.0f}) is within {round(spread_pct*100)}% "
                        f"of median sold price (${avg_sold:.0f}). Profit margin will be very thin after fees."
                    )

            analysis.sourcing_results = json.dumps(sourcing)
            db.session.commit()

            # Agent 4: Arbitrage
            arbitrage = calculate_arbitrage(pricing, sourcing, product_info=extracted)
            # Tag whether ROI is based on a real listing price or an AI estimate
            has_real_price = (input_price > 0) or (sourcing.get('cheapest_found', 0) > 0)
            arbitrage['roi_data_source'] = 'real' if has_real_price else 'estimated'
            analysis.arbitrage_result = json.dumps(arbitrage)

            # Trends + Social in parallel (non-blocking — failures are silent)
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_trend = executor.submit(get_trend_data, search_query)
                future_social = executor.submit(get_social_data, search_query)
                trend = future_trend.result()
                social = future_social.result()

            if trend:
                analysis.trend_data = json.dumps(trend)
            if social:
                analysis.social_data = json.dumps(social)

            analysis.status = 'complete'

            from models.user import User
            user = User.query.get(user_id)
            if user:
                user.analyses_used_this_month += 1
            db.session.commit()

            # Trim history to 10 per user
            all_user_analyses = Analysis.query.filter_by(user_id=user_id).order_by(
                Analysis.created_at.desc()
            ).all()
            if len(all_user_analyses) > 10:
                for old in all_user_analyses[10:]:
                    db.session.delete(old)
                db.session.commit()

        except Exception as e:
            try:
                analysis = Analysis.query.get(analysis_id)
                if analysis:
                    analysis.status = 'error'
                    analysis.error_message = str(e)[:1000]
                    db.session.commit()
            except Exception:
                pass


@analysis_bp.route('/submit', methods=['POST'])
@login_required
@limiter.limit("10 per hour")
def submit():
    # Reset monthly counter if we've rolled into a new month
    current_user.reset_monthly_if_needed()
    if not current_user.can_analyse():
        if current_user.subscription_tier == 'free':
            flash("You've used all 3 free analyses this month. Upgrade to Pro for 50/month — includes a 10-day free trial.", 'warning')
        elif current_user.subscription_tier == 'premium':
            flash("You've reached your 300 analyses this month. Need more? Email us at hello@zzi.ai about our Enterprise plan.", 'warning')
        else:
            flash('Monthly analysis limit reached. Your limit resets at the start of next month.', 'warning')
        return redirect(url_for('billing.pricing'))

    image_file = request.files.get('image')
    text_input = request.form.get('description', '').strip()
    link_input = request.form.get('link', '').strip()

    max_len = current_app.config.get('MAX_TEXT_INPUT_LENGTH', 2000)
    if text_input:
        text_input = text_input[:max_len]

    has_image = image_file and image_file.filename

    # 24-hour cooldown: block re-analysis of the same text/link within 24 hours
    raw_for_check = (link_input or text_input)[:4000] if (link_input or text_input) else None
    if raw_for_check and not has_image:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_dupe = Analysis.query.filter(
            Analysis.user_id == current_user.id,
            Analysis.raw_input == raw_for_check,
            Analysis.status == 'complete',
            Analysis.created_at >= cutoff
        ).first()
        if recent_dupe:
            flash("This item was already analysed in the last 24 hours — market prices don't update that fast. "
                  "Check back tomorrow for fresh data.", 'warning')
            return redirect(url_for('analysis.results', id=recent_dupe.id))

    # Image analysis is Premium-only
    if has_image and current_user.subscription_tier not in ('premium',) and not current_user.is_admin:
        flash('Image analysis is a Premium feature. Upgrade to unlock photo-based flip analysis.', 'warning')
        return redirect(url_for('billing.pricing'))
    has_text = bool(text_input)
    has_link = bool(link_input)

    if not (has_image or has_text or has_link):
        flash('Please provide an image, description, or product URL.', 'danger')
        return redirect(url_for('analysis.input_page'))

    image_base64 = None
    image_media_type = None

    if has_image:
        if not allowed_file(image_file.filename):
            flash('Invalid file type. Please upload JPG, PNG, or WebP.', 'danger')
            return redirect(url_for('analysis.input_page'))
        ext = image_file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        upload_folder = current_app.config['UPLOAD_FOLDER']
        image_path = os.path.join(upload_folder, filename)
        image_file.save(image_path)
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        # Validate that the file is actually an image (MIME check via Pillow)
        try:
            img = PilImage.open(io.BytesIO(image_bytes))
            img.verify()
        except Exception:
            os.remove(image_path)
            flash('Invalid image file. Please upload a real JPG, PNG, or WebP.', 'danger')
            return redirect(url_for('analysis.input_page'))
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        media_map = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}
        image_media_type = media_map.get(ext, 'image/jpeg')
        os.remove(image_path)

    input_type = 'image' if has_image else ('link' if has_link else 'text')
    raw_input = (link_input or text_input or image_file.filename or '')[:4000]

    analysis = Analysis(
        user_id=current_user.id,
        input_type=input_type,
        raw_input=raw_input,
        status='processing'
    )
    db.session.add(analysis)
    db.session.commit()

    app_obj = current_app._get_current_object()
    t = Thread(
        target=_run_analysis_bg,
        args=(app_obj, analysis.id, current_user.id, image_base64, image_media_type,
              text_input, link_input, has_text, has_link),
        daemon=True
    )
    t.start()

    return redirect(url_for('analysis.progress', id=analysis.id))


@analysis_bp.route('/')
@login_required
def input_page():
    return render_template('analysis/input.html')


@analysis_bp.route('/progress/<int:id>')
@login_required
def progress(id):
    analysis = Analysis.query.get_or_404(id)
    if analysis.user_id != current_user.id and not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard.home'))
    return render_template('analysis/progress.html', analysis=analysis)


@analysis_bp.route('/status/<int:id>')
@login_required
def status(id):
    analysis = Analysis.query.get_or_404(id)
    if analysis.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    return jsonify({
        'status': analysis.status,
        'error_message': analysis.error_message,
        'extracted_product': analysis.get_extracted() if analysis.extracted_product else None,
        'price_research': analysis.get_pricing() if analysis.price_research else None,
        'sourcing_results': analysis.get_sourcing() if analysis.sourcing_results else None,
        'arbitrage_result': analysis.get_arbitrage() if analysis.arbitrage_result else None,
        'raw_input': analysis.raw_input,
    })


@analysis_bp.route('/results/<int:id>')
@login_required
def results(id):
    analysis = Analysis.query.get_or_404(id)
    if analysis.user_id != current_user.id and not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard.home'))
    return render_template('analysis/results.html', analysis=analysis)


@analysis_bp.route('/export/<int:id>')
@login_required
def export(id):
    """Clean print/PDF export page for Premium users."""
    analysis = Analysis.query.get_or_404(id)
    if analysis.user_id != current_user.id and not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard.home'))
    if current_user.subscription_tier not in ('premium',) and not current_user.is_admin:
        flash('PDF export is a Premium feature. Upgrade to download reports.', 'warning')
        return redirect(url_for('analysis.results', id=id))
    arb      = analysis.get_arbitrage()
    pricing  = analysis.get_pricing()
    sourcing = analysis.get_sourcing()
    extracted = analysis.get_extracted()
    roi      = analysis.get_roi_value()
    url_is_source = sourcing.get('url_is_source', False) if sourcing else False
    return render_template('analysis/export.html',
        analysis=analysis, arb=arb, pricing=pricing,
        sourcing=sourcing, extracted=extracted, roi=roi,
        url_is_source=url_is_source)


@analysis_bp.route('/public/<int:id>')
def public_results(id):
    """View a shared analysis without login."""
    analysis = Analysis.query.get_or_404(id)
    if not analysis.is_public:
        flash('This analysis is not publicly shared.', 'warning')
        return redirect(url_for('auth.landing'))
    return render_template('analysis/results.html', analysis=analysis, public_view=True)


@analysis_bp.route('/<int:id>/toggle_public', methods=['POST'])
@login_required
def toggle_public(id):
    analysis = Analysis.query.get_or_404(id)
    if analysis.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    analysis.is_public = not analysis.is_public
    db.session.commit()
    public_url = url_for('analysis.public_results', id=id, _external=True) if analysis.is_public else None
    return jsonify({'is_public': analysis.is_public, 'public_url': public_url})
