import os
import uuid
import base64
import json
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app import db
from models.analysis import Analysis
from agents.extraction_agent import extract_product_details
from agents.pricing_agent import research_prices
from agents.sourcing_agent import find_sourcing_deals
from agents.arbitrage_agent import calculate_arbitrage

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

            # Agents 2 & 3: Pricing + Sourcing in parallel
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_pricing = executor.submit(research_prices, search_query, extracted)
                future_sourcing = executor.submit(find_sourcing_deals, search_query, 0, extracted)
                pricing = future_pricing.result()
                sourcing = future_sourcing.result()

            analysis.price_research = json.dumps(pricing)
            analysis.sourcing_results = json.dumps(sourcing)
            db.session.commit()

            # Agent 4: Arbitrage
            arbitrage = calculate_arbitrage(pricing, sourcing)
            analysis.arbitrage_result = json.dumps(arbitrage)
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
def submit():
    if not current_user.can_analyse():
        flash('Analysis limit reached. Please upgrade your plan.', 'warning')
        return redirect(url_for('billing.pricing'))

    image_file = request.files.get('image')
    text_input = request.form.get('description', '').strip()
    link_input = request.form.get('link', '').strip()

    max_len = current_app.config.get('MAX_TEXT_INPUT_LENGTH', 2000)
    if text_input:
        text_input = text_input[:max_len]

    has_image = image_file and image_file.filename
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
