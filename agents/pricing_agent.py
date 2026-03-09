import logging
from datetime import datetime
from agents.base import run_with_search, parse_first_json

logger = logging.getLogger(__name__)


def _current_date_range():
    """Return dynamic date range string for search queries (previous year + current year)."""
    now = datetime.utcnow()
    return f"{now.year - 1} {now.year}"

# Category-specific condition multipliers applied to median sold price
# Different product categories depreciate at very different rates
CONDITION_MULTIPLIERS_BY_CATEGORY = {
    'sneakers': {
        # Box premium is enormous in sneaker resale — DS with OG box commands 15%+ over DS without
        'deadstock':     1.15,
        'new with tags': 1.05,
        'mint':          1.05,
        'like new':      0.88,
        'excellent':     0.80,
        'very good':     0.70,
        'good':          0.58,
        'fair':          0.38,
        'poor':          0.18,
        'damaged':       0.12,
    },
    'bags': {
        # Luxury bags hold value well even in used condition; provenance (receipt, cards) matters
        'deadstock':     1.10,
        'new with tags': 1.08,
        'mint':          1.05,
        'like new':      0.95,
        'excellent':     0.87,
        'very good':     0.78,
        'good':          0.67,
        'fair':          0.50,
        'poor':          0.30,
        'damaged':       0.20,
    },
    'watches': {
        # Full set (box + papers) is the single biggest value driver in watches
        'deadstock':     1.15,
        'new with tags': 1.12,
        'mint':          1.10,
        'like new':      0.92,
        'excellent':     0.85,
        'very good':     0.78,
        'good':          0.70,
        'fair':          0.55,
        'poor':          0.35,
        'damaged':       0.20,
    },
    'electronics': {
        # Electronics depreciate fastest — buyers demand near-perfect condition for near-new prices
        'deadstock':     1.00,
        'new with tags': 1.00,
        'mint':          0.95,
        'like new':      0.87,
        'excellent':     0.78,
        'very good':     0.68,
        'good':          0.56,
        'fair':          0.40,
        'poor':          0.22,
        'damaged':       0.12,
    },
    'clothing': {
        # Clothing markets are saturated; condition matters but less than brand/style
        'deadstock':     1.05,
        'new with tags': 1.05,
        'mint':          1.02,
        'like new':      0.88,
        'excellent':     0.78,
        'very good':     0.67,
        'good':          0.54,
        'fair':          0.36,
        'poor':          0.18,
        'damaged':       0.10,
    },
    'collectibles': {
        # Collectibles: packaging and completeness dominate value
        'deadstock':     1.20,
        'new with tags': 1.15,
        'mint':          1.10,
        'like new':      0.90,
        'excellent':     0.82,
        'very good':     0.72,
        'good':          0.60,
        'fair':          0.42,
        'poor':          0.25,
        'damaged':       0.15,
    },
    'default': {
        'deadstock':     1.10,
        'new with tags': 1.00,
        'new':           1.00,
        'mint':          1.00,
        'like new':      0.90,
        'excellent':     0.88,
        'very good':     0.78,
        'good':          0.72,
        'fair':          0.58,
        'poor':          0.35,
        'damaged':       0.30,
    },
}


def _get_category_key(product_type: str) -> str:
    pt = product_type.lower()
    if any(k in pt for k in ['sneaker', 'shoe', 'trainer', 'boot', 'sandal', 'jordan', 'yeezy']):
        return 'sneakers'
    if any(k in pt for k in ['bag', 'handbag', 'purse', 'wallet', 'backpack', 'tote', 'clutch']):
        return 'bags'
    if 'watch' in pt:
        return 'watches'
    if any(k in pt for k in ['phone', 'laptop', 'tablet', 'console', 'electronic', 'camera', 'headphone', 'airpod', 'ipad', 'iphone', 'macbook', 'playstation', 'xbox']):
        return 'electronics'
    if any(k in pt for k in ['clothing', 'jacket', 'shirt', 'hoodie', 'dress', 'jeans', 'coat', 'top', 'trousers', 'sweatshirt', 'knitwear', 'sweater', 'vest', 'shorts']):
        return 'clothing'
    if any(k in pt for k in ['card', 'toy', 'figure', 'collectible', 'lego', 'funko', 'vinyl', 'trading']):
        return 'collectibles'
    return 'default'


# Seasonal patterns by category: peak/trough months and their impact
SEASONAL_PATTERNS = {
    'sneakers': {
        'peak': [8, 9, 11, 12],      # Back-to-school + holiday gifting
        'trough': [1, 2, 6],          # Post-holiday, summer lull
        'note': 'Sneaker prices peak Aug-Sep (back-to-school) and Nov-Dec (gifting). Currently {status}.',
    },
    'clothing': {
        'peak': [3, 4, 9, 10],       # Season transitions (spring/fall shopping)
        'trough': [1, 2, 7, 8],      # Post-holiday, mid-season
        'note': 'Clothing peaks during season transitions (Mar-Apr, Sep-Oct). Winter gear peaks Oct-Dec, summer gear peaks Apr-Jun. Currently {status}.',
    },
    'electronics': {
        'peak': [11, 12],            # Holiday gifting
        'trough': [9, 10],           # New model launches crater used prices
        'note': 'Electronics drop 15-25% when new models launch (Sep-Oct). Holiday demand offsets in Nov-Dec. Currently {status}.',
    },
    'watches': {
        'peak': [4, 5, 12],          # Watches & Wonders + holiday
        'trough': [1, 2, 7, 8],      # Post-holiday, summer
        'note': 'Watch prices peak around Watches & Wonders (April) and holidays. Q1 and summer are buying opportunities. Currently {status}.',
    },
    'bags': {
        'peak': [9, 10, 11, 12],     # Fall fashion + holidays
        'trough': [1, 2, 6, 7],      # Post-holiday, summer
        'note': 'Luxury bag prices peak Sep-Dec (fall fashion + gifting). Best deals in Jan-Feb post-holiday. Currently {status}.',
    },
    'collectibles': {
        'peak': [11, 12],            # Holiday gifting
        'trough': [1, 2, 3],         # Post-holiday sell-off
        'note': 'Collectibles peak Nov-Dec (holiday gifts). Post-holiday Jan-Feb sees sell-off and lower prices. Currently {status}.',
    },
}


def _get_seasonal_context(product_type: str) -> str:
    """Return seasonal context string for the current month."""
    month = datetime.utcnow().month
    cat = _get_category_key(product_type)
    pattern = SEASONAL_PATTERNS.get(cat)
    if not pattern:
        return ""
    if month in pattern.get('peak', []):
        status = "IN PEAK SEASON — prices are elevated, good time to sell, bad time to buy"
    elif month in pattern.get('trough', []):
        status = "IN TROUGH — prices are depressed, good time to buy, hold for peak to sell"
    else:
        status = "in neutral season — normal pricing expected"
    return pattern.get('note', '').format(status=status)


def _get_condition_multiplier(condition: str, product_type: str = '') -> float:
    cat_key = _get_category_key(product_type)
    multipliers = CONDITION_MULTIPLIERS_BY_CATEGORY.get(cat_key, CONDITION_MULTIPLIERS_BY_CATEGORY['default'])
    c = condition.lower().strip()
    for key, mult in multipliers.items():
        if key in c:
            return mult
    return 0.80  # default: assume lightly used if unknown


def _get_category_platforms(product_type: str) -> str:
    """Return platform-specific search queries for category."""
    cat = _get_category_key(product_type)
    dr = _current_date_range()
    if cat == 'sneakers':
        return [
            f'"{{q}} sold StockX last sale {dr}"',
            f'"{{q}} sold GOAT {dr}"',
            f'"{{q}} sold eBay USA sneakers completed listing {dr}"',
            f'"{{q}} Flight Club sold price"',
            f'"{{q}} Kicks Crew sold price"',
            f'"{{q}} Depop sold {dr}"',
            f'"{{q}} Poshmark sold {dr}"',
            f'"{{q}} price history trend {dr}"',
        ]
    elif cat == 'bags':
        return [
            f'"{{q}} sold Vestiaire Collective {dr}"',
            f'"{{q}} sold Fashionphile price {dr}"',
            f'"{{q}} Rebag value {dr}"',
            f'"{{q}} sold eBay USA completed listing {dr}"',
            f'"{{q}} sold Poshmark {dr}"',
            f'"{{q}} 1stDibs sold price"',
            f'"{{q}} resale value {dr}"',
            f'"{{q}} pre-owned price estimate {dr}"',
        ]
    elif cat == 'watches':
        return [
            f'"{{q}} sold Chrono24 price {dr}"',
            f'"{{q}} WatchFinder sold price {dr}"',
            f'"{{q}} sold eBay USA completed listing {dr}"',
            f'"{{q}} Watchbox trade-in value {dr}"',
            f'"{{q}} sold price {dr} used market"',
            f'"{{q}} auction result {dr}"',
            f'"{{q}} grey market price {dr}"',
            f'"{{q}} resale value box papers vs no box"',
        ]
    elif cat == 'electronics':
        return [
            f'"{{q}} sold eBay USA completed listing {dr}"',
            f'"{{q}} Swappa sold price {dr}"',
            f'"{{q}} Back Market price {dr}"',
            f'"{{q}} Decluttr value {dr}"',
            f'"{{q}} used price USA {dr}"',
            f'"{{q}} Mercari sold {dr}"',
            f'"{{q}} Facebook Marketplace sold price"',
            f'"{{q}} price history depreciation chart {dr}"',
        ]
    else:
        return [
            f'"{{q}} sold eBay USA completed listing {dr}"',
            f'"{{q}} Poshmark sold {dr}"',
            f'"{{q}} Depop sold"',
            f'"{{q}} Mercari sold USA"',
            f'"{{q}} StockX sold" OR "{{q}} GOAT sold"',
            f'"{{q}} Vestiaire Collective sold"',
            f'"{{q}} resale price {dr}"',
            f'"{{q}} price history USA {dr}"',
        ]


def research_prices(search_query, product_info):
    """Research sold prices with expert chain-of-thought reasoning and category-specific platform targeting."""
    try:
        brand        = product_info.get('brand', '')
        product_type = product_info.get('product_type', '')
        era          = product_info.get('era', '')
        style        = ', '.join(product_info.get('style_descriptors', []))
        condition    = product_info.get('condition', 'Unknown')
        size         = product_info.get('size', '')
        limited      = product_info.get('limited_edition', False)
        packaging    = product_info.get('packaging_completeness', '')
        release_year = product_info.get('release_year', era)
        demand_level = product_info.get('demand_level', 'medium')

        cat_key  = _get_category_key(product_type)
        cond_mult = _get_condition_multiplier(condition, product_type)

        limited_note = (
            " LIMITED EDITION / collab / sold-out release — prices typically 1.5–5× retail, "
            "highly volatile. Prioritise StockX and GOAT last-sale data. Check price history graph for trend direction."
        ) if limited else ""

        packaging_note = ""
        if packaging and cat_key in ('sneakers', 'watches', 'bags', 'collectibles'):
            packaging_note = f"\nPACKAGING: {packaging} — factor this into price adjustment (completeness affects value significantly for this category)."

        is_luxury = brand.lower() in [
            'balenciaga', 'gucci', 'louis vuitton', 'chanel', 'hermes', 'hermès',
            'prada', 'dior', 'fendi', 'givenchy', 'bottega veneta', 'celine',
            'saint laurent', 'ysl', 'valentino', 'versace', 'burberry', 'loewe',
            'off-white', 'rick owens', 'chrome hearts', 'loro piana', 'amiri',
            'jacquemus', 'miu miu', 'alexander mcqueen', 'mcm', 'coach', 'kate spade'
        ]
        luxury_note = (
            "LUXURY brand — primary resale venues: Vestiaire Collective, Fashionphile, "
            "Rebag, 1stDibs. Typical range $300–$10,000+. Always use COMPLETED/SOLD prices only."
        ) if is_luxury else ""

        seasonal_context = _get_seasonal_context(product_type)

        size_note      = f" | Size: {size}"      if size      else ""
        condition_note = f" | Condition: {condition}" if condition else ""
        demand_note    = f" | Demand: {demand_level}"

        # Category-specific multiplier range for prompt context
        cat_mult_table = {
            'sneakers':     'DS=1.15, LN=0.88, EX=0.80, VG=0.70, G=0.58, F=0.38, P=0.18',
            'bags':         'DS=1.10, LN=0.95, EX=0.87, VG=0.78, G=0.67, F=0.50, P=0.30',
            'watches':      'DS(full set)=1.15, LN=0.92, EX=0.85, VG=0.78, G=0.70, F=0.55',
            'electronics':  'New=1.00, LN=0.87, EX=0.78, VG=0.68, G=0.56, F=0.40, P=0.22',
            'clothing':     'NWT=1.05, LN=0.88, EX=0.78, VG=0.67, G=0.54, F=0.36',
            'collectibles': 'DS=1.20, LN=0.90, EX=0.82, VG=0.72, G=0.60, F=0.42',
            'default':      'DS=1.10, LN=0.90, EX=0.88, VG=0.78, G=0.72, F=0.58, P=0.35',
        }
        cat_mults_str = cat_mult_table.get(cat_key, cat_mult_table['default'])

        prompt = f"""You are a professional resale market analyst and pricing specialist. You find actual sold transaction data and build evidence-based price estimates.

PRODUCT: "{search_query}"
Brand: {brand} | Type: {product_type} | Era/Release: {release_year} | Style: {style}{size_note}{condition_note}{demand_note}
{luxury_note}{limited_note}{packaging_note}

━━━ STEP 1 — IDENTIFY EXACTLY ━━━
State the precise product: full name, variant/colorway, size, release year. Confirm this is the US resale market.

━━━ STEP 2A — SEARCH FOR CONDITION-MATCHED SOLD PRICES (PRIMARY) ━━━
Search ONLY for COMPLETED/SOLD transactions — NOT active listings.
The item condition is: {condition}

YOUR PRIMARY GOAL: find sold prices for items in the SAME OR VERY SIMILAR condition as this item.
Condition-matched data is far more accurate than applying a multiplier to new/DS prices.

RECENCY: Last 90 days is worth 3× more than older data. Flag any data older than 90 days clearly.

Run these condition-specific searches first:
1. "{search_query} sold eBay USA completed listing {_current_date_range()}"
2. "{search_query} sold price {_current_date_range()}"
3. "{search_query} StockX last sale" (if applicable for this item type)
4. "{search_query} GOAT sold" (if applicable)
5. "{search_query} Poshmark sold {_current_date_range()}"
6. "{search_query} Mercari sold USA {_current_date_range()}"
7. "{search_query} Vestiaire Fashionphile Rebag sold" (if luxury/bag/watch)
8. "{search_query} resale price history {_current_date_range()}"

Note: The search_query already includes the condition grade — your results should surface condition-matched listings.

━━━ STEP 2B — FALLBACK: BASE CONDITION DATA (ONLY IF STEP 2A IS SPARSE) ━━━
If you found fewer than 3 condition-matched data points above, ALSO search for DS/LN/New prices as a baseline:
- Strip the condition grade from the search query and search for the item in best condition
- You will apply a multiplier in Step 4 to adjust down to the actual item condition
- Label all fallback data clearly as "BASE CONDITION — multiplier will be applied"

━━━ STEP 3 — EVIDENCE LOG ━━━
List each data point found. Be specific:
Format: [Platform] [Month/Year] [EXACT condition of that sold item] → $[Price] [ACTUAL or ESTIMATED]
Minimum 3 data points. Label each as CONDITION-MATCHED or BASE-CONDITION.
If condition-matched data is sparse, note "Falling back to base condition + multiplier" explicitly.

Rate your evidence quality:
- STRONG: 3+ condition-matched actual sales from last 90 days
- GOOD: 1–2 condition-matched + recent training knowledge, OR 3+ base-condition actual sales
- MODERATE: Primarily base-condition data + multiplier, or older data
- WEAK: Pure estimation

━━━ STEP 4 — CONDITION ADJUSTMENT (SKIP IF CONDITION-MATCHED DATA FOUND) ━━━
Item condition: {condition}
Category ({cat_key}) multiplier scale: {cat_mults_str}
Fallback multiplier for this item: ×{cond_mult:.2f}

DECISION RULE:
→ If you found 3+ condition-matched data points in Step 2A: use those prices directly as your evidence. Set condition_multiplier = 1.0 in output. Do NOT apply any multiplier.
→ If you found fewer than 3 condition-matched points: apply ×{cond_mult:.2f} to the base-condition median price to get the condition-adjusted estimate. Set condition_multiplier = {cond_mult:.2f} in output.

This prevents double-discounting (applying a multiplier to prices that are already condition-adjusted).

━━━ SEASONAL & SUPPLY CONTEXT ━━━
{f'SEASONAL: {seasonal_context}' if seasonal_context else 'No strong seasonal pattern for this category.'}
If the item is seasonal, adjust sell_velocity_days and recommended_sell_price accordingly.
Off-season items take 2-3x longer to sell and typically sell for 10-20% below peak.

SUPPLY DEPTH: Also estimate how many ACTIVE (unsold) listings you saw for this item across platforms:
- Under 5: SCARCE — seller has pricing power, can list near price_range_high
- 5-20: NORMAL — competitive, recommended_sell_price is appropriate
- 20-50: OVERSUPPLIED — need to undercut, lean toward price_range_low
- 50+: SATURATED — heavy competition, sell at price_range_low or hold for supply to clear
Report this as supply_depth in your output.

━━━ STEP 5 — PRICE CALCULATION ━━━
From your evidence:
- min_sold: 10th-percentile of condition-adjusted prices (what it sells for on a bad day)
- max_sold: 90th-percentile (what it sells for in perfect circumstances)
- avg_sold: median of condition-adjusted prices (realistic central expectation)
- recommended_sell_price: the realistic price a typical seller will ACTUALLY achieve — not the ceiling, not the peak comp.
  Base formula: avg_sold × 0.82, rounded to nearest $5.
  Then apply sell-velocity adjustment:
    • sell_velocity_days ≤ 14: no change (fast mover — 0.82 is competitive enough)
    • sell_velocity_days 15–28: multiply by 0.95 (slow mover — needs a price edge to cut through competition)
    • sell_velocity_days ≥ 29:  multiply by 0.90 (very slow — must price below the pack to move in reasonable time)
  Why: avg_sold is the 50th-percentile, but most sellers face competition, imperfect photos, and off-peak timing. 0.82× of median reliably sells within 2–3 weeks for a normal seller. Listing at the median or above leads to sitting inventory.
- price_range_low: "price to move within a week" floor — avg_sold × 0.68 (use when seller needs quick cash or item is sitting)
- price_range_high: optimistic ceiling — avg_sold × 1.05, never exceed max_sold (requires perfect condition, pro photos, peak timing, and patience)
- sell_velocity_days: realistic days from listing to sale for a competitively priced item at recommended_sell_price
- price_trend: "rising" / "stable" / "falling" / "volatile"
- price_trend_detail: WHY is it trending that way? (e.g. "Rising — celebrity wore this model in September 2024, driving 30% price increase on StockX"; "Falling — new colourway released, original now oversupplied on eBay")

CRITICAL RULES:
- NEVER output 0 for any price field
- recommended_sell_price must be between price_range_low and price_range_high
- confidence must honestly reflect your evidence quality: "high" = multiple real recent sales; "medium" = some data or good comparable estimates; "low" = pure estimate

━━━ OUTPUT ━━━
CRITICAL: Output ONLY the raw JSON object. No markdown fences. Start directly with {{ and end with }}.
{{
  "currency": "USD",
  "min_sold": 0,
  "max_sold": 0,
  "avg_sold": 0,
  "recommended_sell_price": 0,
  "price_range_low": 0,
  "price_range_high": 0,
  "condition_multiplier": {cond_mult:.2f},
  "sell_velocity_days": 14,
  "confidence": "medium",
  "evidence": [
    {{"platform": "eBay", "date": "2025-01", "condition": "Good", "price": 0, "note": "actual or estimated"}}
  ],
  "sources": [
    {{"platform": "eBay", "price": 0, "url": "", "date": "2025-01", "title": "sold listing title"}}
  ],
  "auction_prices": [],
  "market_notes": "Evidence-based market commentary: what you found, data quality, recency, any caveats. Be specific.",
  "price_trend": "stable",
  "price_trend_detail": "Explanation of why prices are moving in this direction and what to expect",
  "data_quality_score": 5,
  "seasonal_note": "",
  "supply_depth": "normal",
  "active_listings_approx": 15
}}

Field notes:
- data_quality_score: 1–10 (10 = multiple confirmed recent sales across 3+ platforms; 1 = pure guess)
- seasonal_note: any seasonal factor (e.g. "Winter coats peak November–January, currently off-season — expect 15% below avg")
- supply_depth: "scarce" / "normal" / "oversupplied" / "saturated" — based on active listing count
- active_listings_approx: your estimate of total active listings across all platforms
- Fill ALL values with real calculated numbers. The zeros are placeholders only."""

        raw = run_with_search(prompt=prompt, use_search=True, max_tokens=8192)
        logger.info(f"Pricing raw response (first 500): {raw[:500]}")
        result = parse_first_json(raw)
        if result:
            # Ensure price_range fields exist
            if not result.get('price_range_low') and result.get('avg_sold'):
                result['price_range_low']  = round(result['avg_sold'] * 0.68, 2)
                result['price_range_high'] = round(min(result['avg_sold'] * 1.05, result.get('max_sold', result['avg_sold'])), 2)
            # If recommended_sell_price is suspiciously close to avg_sold (AI ignored the 0.82 rule), clamp it
            if result.get('recommended_sell_price') and result.get('avg_sold'):
                ceiling = result['avg_sold'] * 0.88  # absolute max we allow
                if result['recommended_sell_price'] > ceiling:
                    result['recommended_sell_price'] = round(result['avg_sold'] * 0.82, 2)
            # condition_multiplier = 1.0 means the AI used condition-matched data directly (correct)
            # None/0/missing means it wasn't set — use our calculated fallback
            cm = result.get('condition_multiplier')
            if cm is None or cm == 0:
                result['condition_multiplier'] = cond_mult

            # Supply depth adjustment: if oversupplied/saturated, reduce recommended_sell_price
            supply = result.get('supply_depth', 'normal')
            if supply in ('oversupplied', 'saturated') and result.get('recommended_sell_price'):
                discount = 0.93 if supply == 'oversupplied' else 0.88
                result['recommended_sell_price'] = round(result['recommended_sell_price'] * discount, 2)
                result['sell_velocity_days'] = max(result.get('sell_velocity_days', 14), 21)

            # Retry if still all zeros
            if not result.get('avg_sold') and not result.get('recommended_sell_price'):
                logger.warning("Pricing returned all zeros — retrying knowledge-only")
                fallback_prompt = f"""You are a resale pricing expert. What is the typical US resale price range for "{search_query}" in {_current_date_range()}?

Brand: {brand} | Type: {product_type} | Condition: {condition}

Think through what you know about this item's resale market. List 3 estimated sold price examples from your training knowledge, then calculate your best estimate.

Return ONLY valid JSON (no markdown):
{{
  "currency": "USD",
  "min_sold": 0,
  "max_sold": 0,
  "avg_sold": 0,
  "recommended_sell_price": 0,
  "price_range_low": 0,
  "price_range_high": 0,
  "condition_multiplier": {cond_mult:.2f},
  "sell_velocity_days": 21,
  "confidence": "low",
  "evidence": [{{"platform": "estimate", "date": "2025", "condition": "{condition}", "price": 0, "note": "estimated"}}],
  "sources": [],
  "auction_prices": [],
  "market_notes": "Estimated from training knowledge — live search data unavailable",
  "price_trend": "stable",
  "price_trend_detail": "Insufficient data for trend analysis",
  "data_quality_score": 2,
  "seasonal_note": ""
}}

Replace all zeros with REAL estimates based on your knowledge. NEVER output 0 for prices."""
                raw2 = run_with_search(prompt=fallback_prompt, use_search=False, max_tokens=1500, fast=True)
                result2 = parse_first_json(raw2)
                if result2 and result2.get('avg_sold', 0) > 0:
                    result2['confidence'] = 'low'
                    result2.setdefault('condition_multiplier', cond_mult)
                    result2.setdefault('data_quality_score', 2)
                    return result2
            return result
        else:
            logger.error(f"Pricing: no JSON found. Raw: {raw[:500]}")

    except Exception as e:
        logger.error(f"Pricing agent error: {e}")

    return {
        "currency": "USD",
        "min_sold": 0,
        "max_sold": 0,
        "avg_sold": 0,
        "recommended_sell_price": 0,
        "price_range_low": 0,
        "price_range_high": 0,
        "condition_multiplier": 0.80,
        "sell_velocity_days": 0,
        "confidence": "low",
        "evidence": [],
        "sources": [],
        "auction_prices": [],
        "market_notes": "Could not retrieve pricing data.",
        "price_trend": "stable",
        "price_trend_detail": "",
        "data_quality_score": 1,
        "seasonal_note": "",
        "supply_depth": "normal",
        "active_listings_approx": 0
    }
