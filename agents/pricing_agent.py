import logging
from agents.base import run_with_search, parse_first_json

logger = logging.getLogger(__name__)

# Condition multipliers applied to median sold price to get condition-adjusted value
CONDITION_MULTIPLIERS = {
    'new':           1.00,
    'new with tags': 1.00,
    'mint':          1.00,
    'deadstock':     1.10,  # unworn with original packaging commands premium
    'like new':      0.90,
    'excellent':     0.88,
    'very good':     0.78,
    'good':          0.72,
    'fair':          0.58,
    'poor':          0.35,
    'damaged':       0.30,
}

def _get_condition_multiplier(condition: str) -> float:
    c = condition.lower().strip()
    for key, mult in CONDITION_MULTIPLIERS.items():
        if key in c:
            return mult
    return 0.80  # default: assume lightly used if unknown


def research_prices(search_query, product_info):
    """Research sold prices across US platforms with chain-of-thought reasoning."""
    try:
        brand        = product_info.get('brand', '')
        product_type = product_info.get('product_type', '')
        era          = product_info.get('era', '')
        style        = ', '.join(product_info.get('style_descriptors', []))
        condition    = product_info.get('condition', 'Unknown')
        size         = product_info.get('size', '')
        limited      = product_info.get('limited_edition', False)

        cond_mult = _get_condition_multiplier(condition)

        limited_note = (
            " LIMITED EDITION / collab / sold-out release — prices typically 2–5× retail, "
            "highly volatile. Check StockX and GOAT last-sale data specifically."
        ) if limited else ""

        is_luxury = brand.lower() in [
            'balenciaga', 'gucci', 'louis vuitton', 'chanel', 'hermes', 'hermès',
            'prada', 'dior', 'fendi', 'givenchy', 'bottega veneta', 'celine',
            'saint laurent', 'ysl', 'valentino', 'versace', 'burberry', 'loewe',
            'off-white', 'rick owens', 'chrome hearts', 'loro piana'
        ]
        luxury_note = (
            "LUXURY brand — primary resale venues: Vestiaire Collective, Fashionphile, "
            "Rebag, 1stDibs, The RealReal. Typical range $300–$5000+. "
            "Always use COMPLETED/SOLD prices only."
        ) if is_luxury else ""

        size_note      = f" | Size: {size}"      if size      else ""
        condition_note = f" | Condition: {condition}" if condition else ""

        prompt = f"""You are a professional US resale market analyst. Use a strict chain-of-thought process before outputting your final answer.

PRODUCT: "{search_query}"
Brand: {brand} | Type: {product_type} | Era: {era} | Style: {style}{size_note}{condition_note}
{luxury_note}{limited_note}

━━━ STEP 1 — IDENTIFY EXACTLY ━━━
State the precise product name, variant/colorway, and size you are researching. Confirm the US market context.

━━━ STEP 2 — SEARCH FOR SOLD EVIDENCE ━━━
Search ONLY for COMPLETED/SOLD transactions — NOT active listings. Sold prices = what buyers actually paid. Active listing prices = what sellers hope to get. These are very different.

Run these searches:
1. "{search_query} sold eBay USA completed listing 2024 2025"
2. "{search_query} {condition} sold price eBay"
3. "{search_query} StockX last sale price"
4. "{search_query} GOAT sold"
5. "{search_query} Poshmark sold"
6. "{search_query} Mercari sold USA"
7. "{search_query} The RealReal sold"
8. "{search_query} resale price history 2024 2025"

━━━ STEP 3 — LIST YOUR EVIDENCE ━━━
Before calculating, explicitly list the sold transactions you found or know about:
Format each as: [Platform] [Approx date] [Condition] → $[Price]
List a minimum of 3 examples. If you cannot find exact matches, list the closest comparable sold items you know from training data and note they are estimates.

━━━ STEP 4 — CONDITION ADJUSTMENT ━━━
The item condition is: {condition}
Apply this adjustment to the median sold price:
- New/Mint/Deadstock: ×1.00–1.10
- Like New/Excellent: ×0.88–0.90
- Very Good/Good:     ×0.72–0.78
- Fair/Acceptable:    ×0.58–0.65
- Poor/Damaged:       ×0.30–0.40
Estimated multiplier for this item: ×{cond_mult:.2f}

━━━ STEP 5 — CALCULATE ━━━
From your evidence:
- min_sold: 10th-percentile of your found prices (condition-adjusted)
- max_sold: 90th-percentile (condition-adjusted)
- avg_sold: median of your found prices × condition multiplier
- recommended_sell_price: avg_sold × 0.88, rounded to nearest $5 (accounts for competition and platform variability)
- price_range_low: conservative realistic sell (avg_sold × 0.75)
- price_range_high: optimistic realistic sell (avg_sold × 1.10, never exceed max_sold)
- sell_velocity_days: estimate how many days this typically sits before selling (use demand knowledge)
- confidence: "high" = multiple recent actual sales found, "medium" = some data / estimates from training, "low" = pure estimate

CRITICAL RULES:
- NEVER output 0 for any price field — always provide a real number
- Set confidence based on how much real evidence you actually found
- recommended_sell_price must be between min_sold and max_sold

━━━ OUTPUT ━━━
CRITICAL: Output ONLY the raw JSON object. Do NOT wrap in markdown code fences. Do NOT add any text before or after. Start your response directly with {{ and end with }}.
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
    {{"platform": "eBay", "price": 0, "url": "", "date": "2025-01", "title": "example sold listing"}}
  ],
  "auction_prices": [],
  "market_notes": "Evidence-based market commentary: what you found, confidence level, and any caveats",
  "price_trend": "stable"
}}

Fill ALL values with real calculated numbers. The zeros shown above are placeholders only."""

        raw = run_with_search(prompt=prompt, use_search=True, max_tokens=8192)
        logger.info(f"Pricing raw response (first 500): {raw[:500]}")
        result = parse_first_json(raw)
        if result:
            # Ensure price_range fields exist for backwards compatibility
            if not result.get('price_range_low') and result.get('avg_sold'):
                result['price_range_low']  = round(result['avg_sold'] * 0.75, 2)
                result['price_range_high'] = round(min(result['avg_sold'] * 1.10, result.get('max_sold', result['avg_sold'])), 2)
            if not result.get('condition_multiplier'):
                result['condition_multiplier'] = cond_mult

            # Retry if still all zeros
            if not result.get('avg_sold') and not result.get('recommended_sell_price'):
                logger.warning("Pricing returned all zeros — retrying knowledge-only")
                fallback_prompt = f"""What is the typical US resale price range for "{search_query}" in 2024–2025?
Brand: {brand} | Type: {product_type} | Condition: {condition}

Think through what you know about this item's resale market in the USA. List 2–3 sold price examples from your training data, then give your best estimate.

Return ONLY valid JSON:
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
  "confidence": "low",
  "evidence": [],
  "sources": [],
  "auction_prices": [],
  "market_notes": "Estimated from model training knowledge — live search unavailable",
  "price_trend": "stable"
}}

Replace zeros with your REAL estimates. NEVER output 0."""
                raw2 = run_with_search(prompt=fallback_prompt, use_search=False, max_tokens=1200, fast=True)
                result2 = parse_first_json(raw2)
                if result2 and result2.get('avg_sold', 0) > 0:
                    result2['confidence'] = 'low'
                    if not result2.get('condition_multiplier'):
                        result2['condition_multiplier'] = cond_mult
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
        "price_trend": "stable"
    }
