import json
import logging
from agents.base import run_with_search, parse_first_json

logger = logging.getLogger(__name__)

# eBay category-specific fees: Final Value Fee + 2.35% Managed Payments processing
EBAY_FEES_BY_CATEGORY = {
    'sneakers':     0.080 + 0.0235,   # 8% FVF + 2.35% payment = 10.35%
    'electronics':  0.1325 + 0.0235,  # 13.25% + 2.35% = 15.60%
    'bags':         0.1325 + 0.0235,
    'watches':      0.1325 + 0.0235,
    'clothing':     0.1325 + 0.0235,
    'collectibles': 0.1325 + 0.0235,
    'default':      0.1350 + 0.0235,  # 13.5% + 2.35% = 15.85%
}

# All platform fees (total seller cost including payment processing)
PLATFORM_FEES = {
    'eBay':        None,      # category-specific, resolved at runtime
    'Depop':       0.10,      # 10% seller fee (includes payment processing)
    'Poshmark':    0.20,      # 20% commission
    'StockX':      0.125,     # 9.5% seller fee + 3% payment processing
    'Mercari':     0.10,      # 10% seller fee
    'Grailed':     0.119,     # 9% commission + 2.9% payment processing
    'Swappa':      0.03,      # 3% seller fee (electronics only)
    'Back Market': 0.10,      # ~10% commission (electronics only)
    'Chrono24':    0.065,     # 6.5% seller fee (watches only)
    'Vestiaire Collective': 0.12,  # ~12% commission (luxury bags/fashion)
    'Fashionphile': 0.15,    # ~15% consignment (luxury bags)
    'Rebag':       0.15,     # ~15% consignment (luxury bags)
    "Sotheby's":   0.20,     # ~20% effective seller cost (auction houses)
    'Heritage Auctions': 0.20,  # ~20% effective seller cost
    "Christie's":  0.20,     # ~20% effective seller cost
    'Facebook Marketplace': 0.0,  # 0% local pickup
    'OfferUp':     0.0,      # 0% local pickup
    'Chairish':    0.20,     # ~20% consignment (furniture/decor)
}


def _get_ebay_fee(product_info: dict) -> float:
    pt = (product_info.get('product_type', '') or '').lower()
    if any(k in pt for k in ['sneaker', 'shoe', 'trainer', 'boot', 'sandal', 'jordan', 'yeezy']):
        return EBAY_FEES_BY_CATEGORY['sneakers']
    if any(k in pt for k in ['phone', 'smartphone', 'laptop', 'tablet', 'console', 'electronic', 'camera', 'headphone', 'airpod', 'ipad', 'iphone', 'macbook', 'playstation', 'xbox', 'computer', 'gaming']):
        return EBAY_FEES_BY_CATEGORY['electronics']
    if any(k in pt for k in ['bag', 'handbag', 'purse', 'wallet', 'backpack', 'tote']):
        return EBAY_FEES_BY_CATEGORY['bags']
    if 'watch' in pt:
        return EBAY_FEES_BY_CATEGORY['watches']
    if any(k in pt for k in ['clothing', 'jacket', 'shirt', 'hoodie', 'dress', 'jeans', 'coat', 'top', 'trousers', 'sweatshirt']):
        return EBAY_FEES_BY_CATEGORY['clothing']
    if any(k in pt for k in ['card', 'toy', 'figure', 'collectible', 'lego', 'funko', 'vinyl', 'trading']):
        return EBAY_FEES_BY_CATEGORY['collectibles']
    return EBAY_FEES_BY_CATEGORY['default']


def _get_category_key(product_info: dict) -> str:
    """Return category key for platform eligibility checks."""
    pt = (product_info.get('product_type', '') or '').lower()
    if any(k in pt for k in ['sneaker', 'shoe', 'trainer', 'boot', 'sandal', 'jordan', 'yeezy']):
        return 'sneakers'
    if any(k in pt for k in ['bag', 'handbag', 'purse', 'wallet', 'backpack', 'tote']):
        return 'bags'
    if 'watch' in pt:
        return 'watches'
    if any(k in pt for k in ['phone', 'smartphone', 'laptop', 'tablet', 'console', 'electronic', 'camera', 'headphone', 'computer', 'gaming']):
        return 'electronics'
    if any(k in pt for k in ['clothing', 'jacket', 'shirt', 'hoodie', 'dress', 'jeans', 'coat', 'top', 'trousers', 'sweatshirt']):
        return 'clothing'
    if any(k in pt for k in ['card', 'toy', 'figure', 'collectible', 'lego', 'funko']):
        return 'collectibles'
    return 'default'


def _is_platform_eligible(platform: str, product_info: dict) -> bool:
    """Check if a platform is eligible for this item type."""
    condition = (product_info.get('condition_grade', '') or '').lower()
    cat = _get_category_key(product_info)

    if platform == 'StockX':
        # StockX requires deadstock/new items only; sneakers and streetwear focus
        if condition not in ('deadstock', 'new with tags'):
            return False
        return cat in ('sneakers', 'clothing', 'collectibles', 'default')
    if platform == 'Grailed':
        # Grailed is primarily clothing, sneakers, streetwear
        return cat in ('sneakers', 'clothing', 'default')
    if platform == 'Depop':
        # Depop is fashion-focused — not relevant for electronics/watches
        return cat not in ('electronics', 'watches')
    if platform == 'Poshmark':
        # Poshmark is fashion/home — not relevant for electronics
        return cat not in ('electronics',)
    if platform == 'Swappa':
        # Swappa is electronics-only
        return cat == 'electronics'
    if platform == 'Back Market':
        # Back Market is electronics-only
        return cat == 'electronics'
    if platform == 'Chrono24':
        # Chrono24 is watches-only
        return cat == 'watches'
    if platform in ('Vestiaire Collective', 'Fashionphile', 'Rebag'):
        # Luxury consignment — bags, watches, jewelry, high-end fashion
        return cat in ('bags', 'watches', 'clothing')
    if platform in ("Sotheby's", "Christie's", 'Heritage Auctions'):
        # Auction houses — watches, bags, collectibles (not electronics/general clothing)
        return cat in ('watches', 'bags', 'collectibles')
    if platform == 'Chairish':
        # Chairish is furniture/home decor only
        return 'furniture' in (product_info.get('product_type', '') or '').lower()
    # Facebook Marketplace and OfferUp work for everything
    return True


def _validate_and_recalculate(result, pricing_data, sourcing_data, product_info):
    """Recalculate all arithmetic fields deterministically in Python.
    AI provides qualitative assessments; Python guarantees correct math."""

    buy = result.get('buy_price', 0) or 0
    sell = result.get('sell_price', 0) or 0

    # Reconstruct from source data if AI returned bad values
    if sell <= 0:
        sell = pricing_data.get('recommended_sell_price', 0) or (pricing_data.get('avg_sold', 0) * 0.82)
    if buy <= 0:
        buy = sourcing_data.get('cheapest_found', 0) or sourcing_data.get('avg_source_price', 0)
        if buy <= 0:
            buy = (pricing_data.get('avg_sold', 0) or 0) * 0.55

    result['buy_price'] = round(buy, 2)
    result['sell_price'] = round(sell, 2)
    result['gross_profit'] = round(sell - buy, 2)

    # Build platform fee map
    ebay_fee_pct = _get_ebay_fee(product_info)
    platforms = dict(PLATFORM_FEES)
    platforms['eBay'] = ebay_fee_pct

    # Get shipping estimate from AI (or use default)
    shipping = result.get('shipping_cost_est', 10.0) or 10.0

    best_net = float('-inf')
    best_plat = 'eBay'
    breakdown = []

    for plat, fee_pct in platforms.items():
        if not _is_platform_eligible(plat, product_info):
            continue
        fee_amt = round(sell * fee_pct, 2)
        net = round(sell - buy - fee_amt - shipping, 2)
        roi = round((net / buy) * 100, 2) if buy > 0 else 0
        breakdown.append({
            'platform': plat,
            'fee_pct': round(fee_pct * 100, 1),
            'fee_amount': fee_amt,
            'net_profit': net,
            'net_roi': roi
        })
        if net > best_net:
            best_net = net
            best_plat = plat

    result['platform_breakdown'] = breakdown
    result['best_platform'] = best_plat
    best_fee_pct = platforms.get(best_plat, 0.135)
    result['platform_fee'] = round(sell * best_fee_pct, 2)
    result['net_profit'] = round(sell - buy - result['platform_fee'], 2)
    result['true_net_profit'] = round(result['net_profit'] - shipping, 2)

    # Storage cost
    velocity = pricing_data.get('sell_velocity_days', 14) or 14
    storage = min(velocity * 0.50, 15.0)
    result['storage_cost_est'] = round(storage, 2)
    result['true_net_profit_after_storage'] = round(result['true_net_profit'] - storage, 2)

    # Break-even price
    if best_fee_pct < 1:
        result['break_even_price'] = round((buy + shipping) / (1 - best_fee_pct), 2)
    else:
        result['break_even_price'] = 0

    # ROI
    result['roi_percent'] = round((result['true_net_profit'] / buy) * 100, 2) if buy > 0 else 0
    result['capital_at_risk'] = round(buy, 2)

    # Risk-adjusted ROI
    confidence = pricing_data.get('confidence', 'medium')
    conf_factor = {'high': 0.90, 'medium': 0.75, 'low': 0.55}.get(confidence, 0.75)
    result['risk_adjusted_roi'] = round(result['roi_percent'] * conf_factor, 2)

    # Minimum viable ROI by price tier
    if buy < 50:
        result['minimum_viable_roi'] = 60
    elif buy < 200:
        result['minimum_viable_roi'] = 35
    elif buy < 500:
        result['minimum_viable_roi'] = 20
    else:
        result['minimum_viable_roi'] = 15

    # Verdict (deterministic)
    roi = result['roi_percent']
    tnp = result['true_net_profit']
    if roi > 80 and tnp > 0:
        result['verdict'] = 'Strong Flip'
    elif roi >= 35 and tnp > 0:
        result['verdict'] = 'Decent Flip'
    elif roi >= 10 and tnp > 0:
        result['verdict'] = 'Marginal'
    else:
        result['verdict'] = 'Avoid'

    # Risk rating
    avg_sold = pricing_data.get('avg_sold', 1) or 1
    min_sold = pricing_data.get('min_sold', 0) or 0
    max_sold = pricing_data.get('max_sold', 0) or 0
    variance = ((max_sold - min_sold) / avg_sold) if avg_sold > 0 else 0
    auth_risk = sourcing_data.get('authenticity_risk', 'medium')
    if variance > 0.60 or tnp <= 0 or (auth_risk == 'high' and variance > 0.30):
        result['risk_rating'] = 'high'
    elif variance > 0.25 or auth_risk == 'high':
        result['risk_rating'] = 'medium'
    else:
        result['risk_rating'] = 'low'

    # Opportunity score (deterministic)
    score = 50
    if roi > 80:
        score += 20
    elif roi >= 40:
        score += 10
    elif roi < 20:
        score -= 10
    if roi < 0:
        score -= 20
    if confidence == 'high':
        score += 10
    elif confidence == 'low':
        score -= 10
    if velocity < 10:
        score += 10
    elif velocity > 30:
        score -= 10
    if tnp > 100:
        score += 5
    if result['risk_rating'] == 'high':
        score -= 5
    result['opportunity_score'] = max(5, min(95, score))

    # Time and hourly rate
    time_hrs = result.get('estimated_time_hrs', 2.0) or 2.0
    result['estimated_time_hrs'] = time_hrs
    result['net_hourly_rate'] = round(result['true_net_profit'] / time_hrs, 2) if time_hrs > 0 else 0

    # Ensure liquidity score
    if velocity <= 3:
        result['liquidity_score'] = 10
    elif velocity <= 7:
        result['liquidity_score'] = 8
    elif velocity <= 14:
        result['liquidity_score'] = 6
    elif velocity <= 30:
        result['liquidity_score'] = 3
    else:
        result['liquidity_score'] = 1

    return result


def calculate_arbitrage(pricing_data, sourcing_data, product_info=None):
    """Calculate arbitrage profit with Python-validated math and AI qualitative analysis."""
    product_info = product_info or {}
    ebay_fee_pct = _get_ebay_fee(product_info)
    ebay_fee_display = round(ebay_fee_pct * 100, 1)
    cat_key = _get_category_key(product_info)

    # Build platform fees display for prompt
    platform_fees_text = f"""- eBay:     {ebay_fee_display}% (FVF + payment processing, category-specific)
- Depop:    10% (seller fee, includes payment processing)
- Poshmark: 20% (commission)
- StockX:   12.5% (9.5% seller + 3% payment processing)
- Mercari:  10% (seller fee)
- Grailed:  11.9% (9% commission + 2.9% payment processing)"""

    try:
        prompt = f"""You are a professional resale arbitrage analyst. Analyse this flip opportunity and provide strategic advice.

PRICING DATA (what it sells for):
{json.dumps(pricing_data, indent=2)}

SOURCING DATA (what you can buy it for):
{json.dumps(sourcing_data, indent=2)}

PRODUCT INFO:
Category: {cat_key}
Condition: {product_info.get('condition_grade', 'Unknown')}

PLATFORM FEES (for reference — Python will recalculate all math, you just need to understand the landscape):
{platform_fees_text}

NOTE: All numeric calculations (ROI, fees, net profit, verdict, opportunity score) will be recalculated in Python. Your job is to provide:

1. **shipping_cost_est**: Estimate US domestic shipping for this specific item type:
   - Sneakers/shoes: $12-15 | Bags: $12-18 | Clothing: $5-8
   - Electronics: $12-20 | Watches: $8-12 | Bulky: $15-25 | Default: $10

2. **estimated_time_hrs**: Total time investment for this flip:
   - Simple clothing: 1-2 hrs | Sneakers/bags: 2-3 hrs
   - Electronics: 2-4 hrs | Luxury watches: 3-5 hrs

3. **recommendation**: 1-2 SHORT sentences MAXIMUM. Plain English, no jargon. Just say if it's worth buying and the single biggest reason why or why not. Example: "Good flip — buy under $150 and you'll clear $60 profit easily." or "Pass on this one — the buy price is too close to what it sells for." Do NOT write a paragraph.

4. **listing_tips**: 5 specific, actionable tips for THIS exact item:
   - Platform choice (which platform first and why for this item)
   - Title strategy (exact keywords buyers search for)
   - Photography (specific angles and details for this item type)
   - Pricing strategy (BIN vs auction, offer enabled)
   - Trust & authenticity (how to build buyer confidence)

5. **risk_commentary**: Qualitative risk factors the numbers don't capture (authenticity concerns, market saturation, seasonal timing, condition ambiguity).

Return ONLY valid JSON (no markdown):
{{
  "buy_price": 0,
  "sell_price": 0,
  "shipping_cost_est": 10.0,
  "estimated_time_hrs": 2.0,
  "recommendation": "Specific recommendation text",
  "listing_tips": [
    "Platform: [specific reason]",
    "Title: [specific keywords]",
    "Photos: [specific details]",
    "Pricing: [specific strategy]",
    "Trust: [specific advice]"
  ],
  "risk_commentary": "Qualitative risk assessment"
}}

CRITICAL: Set buy_price to cheapest_found from sourcing (or avg_source_price). Set sell_price to recommended_sell_price from pricing. These anchor the Python calculations."""

        raw = run_with_search(prompt=prompt, use_search=False, max_tokens=2500, fast=True)
        logger.info(f"Arbitrage raw response (first 300): {raw[:300]}")
        result = parse_first_json(raw)
        if result:
            # Truncate recommendation to ~2 sentences if AI rambled
            rec = result.get('recommendation', '')
            if rec and len(rec) > 200:
                sentences = rec.split('. ')
                result['recommendation'] = '. '.join(sentences[:2]).rstrip('.') + '.'
            # Python recalculates all math deterministically
            result = _validate_and_recalculate(result, pricing_data, sourcing_data, product_info)
            return result
        else:
            logger.error(f"Arbitrage: no JSON found. Raw: {raw[:500]}")

    except Exception as e:
        logger.error(f"Arbitrage agent error: {e}")

    # Fallback: build entirely from pricing/sourcing data in Python
    ebay_fee_display_safe = round(ebay_fee_pct * 100, 1)
    fallback = {
        "buy_price": 0,
        "sell_price": 0,
        "gross_profit": 0,
        "best_platform": "Unknown",
        "platform_fee": 0,
        "net_profit": 0,
        "shipping_cost_est": 10.0,
        "storage_cost_est": 0,
        "true_net_profit": 0,
        "true_net_profit_after_storage": 0,
        "break_even_price": 0,
        "roi_percent": 0,
        "risk_adjusted_roi": 0,
        "minimum_viable_roi": 0,
        "capital_at_risk": 0,
        "risk_rating": "high",
        "verdict": "Avoid",
        "recommendation": "Insufficient data to calculate arbitrage.",
        "risk_commentary": "",
        "opportunity_score": 0,
        "liquidity_score": 0,
        "estimated_time_hrs": 0,
        "net_hourly_rate": 0,
        "listing_tips": [],
        "platform_breakdown": [],
    }
    # Try to compute from available data
    if pricing_data.get('recommended_sell_price') or sourcing_data.get('cheapest_found'):
        fallback = _validate_and_recalculate(fallback, pricing_data, sourcing_data, product_info)
    return fallback
