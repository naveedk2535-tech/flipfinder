import os
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request

api_bp = Blueprint('api', __name__, url_prefix='/api')


def _check_api_key():
    """Validate Bearer token against FLIPAFIND_API_KEY env var."""
    expected = os.getenv('FLIPAFIND_API_KEY', '')
    if not expected:
        return True  # No key configured = open access
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:] == expected
    return False


@api_bp.route('/trending')
def trending():
    if not _check_api_key():
        return jsonify({'error': 'Unauthorized'}), 401

    from models.analysis import Analysis

    days = int(request.args.get('days', 7))
    limit = min(int(request.args.get('limit', 20)), 50)
    since = datetime.utcnow() - timedelta(days=days)

    analyses = Analysis.query.filter(
        Analysis.status == 'complete',
        Analysis.created_at >= since
    ).order_by(Analysis.created_at.desc()).limit(limit).all()

    results = []
    for a in analyses:
        extracted = a.get_extracted()
        arbitrage = a.get_arbitrage()
        category_label, _ = a.get_category()

        topic = a.get_product_summary()
        if not topic or topic == 'Unknown Product':
            continue

        results.append({
            'topic': topic,
            'category': category_label,
            'brand': extracted.get('brand', ''),
            'model': extracted.get('model', ''),
            'condition': extracted.get('condition', ''),
            'roi_percent': arbitrage.get('roi_percent', 0),
            'buy_price': arbitrage.get('buy_price', 0),
            'sell_price': arbitrage.get('sell_price', 0),
            'source': 'flipafind_analysis',
            'analyzed_at': a.created_at.isoformat()
        })

    return jsonify({
        'results': results,
        'count': len(results),
        'generated_at': datetime.utcnow().isoformat()
    })
