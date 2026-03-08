import json
import logging
from agents.base import run_with_search, parse_first_json

logger = logging.getLogger(__name__)

# eBay category-specific final value fees (as of 2025)
# eBay's sneaker/athletic footwear category has a special reduced fee
EBAY_FEES_BY_CATEGORY = {
    'sneakers':     0.080,   # 8% — eBay sneaker authenticated deals category
    'electronics':  0.1325,  # 13.25%
    'bags':         0.1325,  # 13.25%
    'watches':      0.1325,  # 13.25%
    'clothing':     0.1325,  # 13.25%
    'collectibles': 0.1325,  # 13.25%
    'default':      0.1350,  # 13.5% general category
}


def _get_ebay_fee(product_info: dict) -> float:
    pt = (product_info.get('product_type', '') or '').lower()
    if any(k in pt for k in ['sneaker', 'shoe', 'trainer', 'boot', 'sandal', 'jordan', 'yeezy']):
        return EBAY_FEES_BY_CATEGORY['sneakers']
    if any(k in pt for k in ['phone', 'laptop', 'tablet', 'console', 'electronic', 'camera', 'headphone', 'airpod', 'ipad', 'iphone', 'macbook', 'playstation', 'xbox']):
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


def calculate_arbitrage(pricing_data, sourcing_data, product_info=None):
    """Calculate arbitrage profit with expert P&L, risk-adjusted ROI, and category-accurate fees."""
    product_info = product_info or {}
    ebay_fee_pct = _get_ebay_fee(product_info)
    ebay_fee_display = round(ebay_fee_pct * 100, 1)

    try:
        prompt = f"""You are a professional resale arbitrage analyst. Calculate the complete opportunity from the data below with precise arithmetic. Show your working before outputting JSON.

PRICING DATA (what it sells for):
{json.dumps(pricing_data, indent=2)}

SOURCING DATA (what you can buy it for):
{json.dumps(sourcing_data, indent=2)}

━━━ STEP 1 — SET BASE PRICES ━━━
- buy_price = cheapest_found from sourcing_data
  → If cheapest_found is 0 or missing, use avg_source_price
  → If both are 0, use avg_sold from pricing_data × 0.55 (conservative estimate)
  → If url_is_source=true, the buy_price is the CONFIRMED listing price — use it directly
- sell_price = recommended_sell_price from pricing_data
  → This is already a liquidity-adjusted, conservative sell price (≈82% of median sold). Use it as-is — it represents what a real seller will realistically achieve, not the ceiling.
  → SANITY CHECK: must be ≥ price_range_low and ≤ max_sold. If above max_sold, cap at max_sold. If 0 or missing, use avg_sold × 0.82.
- gross_profit = sell_price − buy_price

Note: If gross_profit is negative, report it accurately — do NOT adjust prices to hide a bad deal.

━━━ STEP 2 — PLATFORM FEE BREAKDOWN (ACCURATE RATES) ━━━
Calculate for each platform using the SELL PRICE:

- eBay:     fee = sell_price × {ebay_fee_pct:.4f}  ({ebay_fee_display}% — category-specific rate)
- Depop:    fee = sell_price × 0.10   (10% seller fee)
- Poshmark: fee = sell_price × 0.20   (20% commission)
- StockX:   fee = sell_price × 0.125  (9.5% seller fee + 3% payment processing = 12.5% total)

net_profit for each = gross_profit − platform_fee

NOTE on StockX: Only include StockX as best_platform if item is in Deadstock condition — StockX requires unworn/unused items. For worn items, exclude StockX from the "best platform" recommendation.

━━━ STEP 3 — SHIPPING & TRUE NET PROFIT ━━━
Estimate US domestic shipping cost based on item type (use product_type from sourcing data):
- Sneakers/shoes:        $12–15 (signature confirmation recommended for items >$100)
- Bags/handbags:         $12–18 (insured shipping strongly recommended)
- Clothing/accessories:  $5–8  (poly mailer, first class)
- Electronics:           $12–20 (double-box required, fragile)
- Watches/jewellery:     $8–12 (insured, discreet packaging)
- Bulky items:           $15–25
- Default:               $10

best_platform = platform with the highest net_profit (after fee, considering condition eligibility)
true_net_profit = best_platform net_profit − shipping_cost_est
break_even_price = (buy_price + shipping_cost_est) / (1 − best_platform_fee_pct), round up

storage_cost_est = sell_velocity_days × 0.50 per day, capped at $15
(Accounts for space, time cost of holding the item until it sells)

true_net_profit_after_storage = true_net_profit − storage_cost_est

━━━ STEP 4 — ROI & RISK ANALYSIS ━━━
roi_percent = (true_net_profit / buy_price) × 100
  → If buy_price = 0, set roi_percent = 0

risk_adjusted_roi = roi_percent × confidence_factor
  → confidence "high" = factor 0.90 (high confidence in prices, small discount)
  → confidence "medium" = factor 0.75
  → confidence "low" = factor 0.55 (significant uncertainty)
  → Use the confidence field from pricing_data

risk_rating:
- "low"    if price variance ((max_sold − min_sold) / avg_sold) < 25%
- "medium" if variance 25–60% OR authenticity_risk is "high" in sourcing
- "high"   if variance > 60%, OR true_net_profit negative, OR authenticity_risk "high" AND variance > 30%

capital_at_risk = buy_price (the maximum you can lose if the item doesn't sell)
minimum_viable_roi: the minimum ROI % that makes this flip worth your time
- If buy_price < $50: need 60%+ ROI (small deals need big % returns to cover effort)
- If buy_price $50–200: need 35%+ ROI
- If buy_price $200–500: need 20%+ ROI (higher $ profit justifies lower %)
- If buy_price > $500: need 15%+ ROI ($100+ absolute profit on quality items is worthwhile)

opportunity_score (0–100): combines ROI, confidence, demand, velocity:
- Start at 50
- +20 if roi_percent > 80%
- +10 if roi_percent 40–80%
- -10 if roi_percent < 20%
- -20 if roi_percent < 0%
- +10 if confidence = "high"
- -10 if confidence = "low"
- +10 if sell_velocity_days < 10 (fast moving)
- -10 if sell_velocity_days > 30 (slow, capital tied up)
- +5 if true_net_profit > $100 (meaningful absolute profit)
- -5 if risk_rating = "high"
- Cap at 95, floor at 5

verdict (be honest, never optimistic when numbers are bad):
- "Strong Flip"  if roi_percent > 80% AND true_net_profit > 0
- "Decent Flip"  if roi_percent 35–80% AND true_net_profit > 0
- "Marginal"     if roi_percent 10–35% AND true_net_profit > 0
- "Avoid"        if roi_percent < 10% OR true_net_profit ≤ 0

IMPORTANT: For high-ticket items (buy_price > $500), a "Decent Flip" at 25%+ ROI is acceptable — absolute dollar profit matters. Mention this in the recommendation.

━━━ STEP 5 — LIQUIDITY & TIME VALUE ━━━
liquidity_score (1–10): How quickly and reliably will this sell?
- Use sell_velocity_days: 1–3 days → 9–10; 4–7 → 7–8; 8–14 → 5–6; 15–30 → 3–4; 30+ → 1–2

estimated_time_hrs: total realistic time investment for this flip:
- Simple clothing/accessories: 1–2 hrs (photograph + list + pack + ship)
- Sneakers/bags: 2–3 hrs (detail photography, authentication photos, listing, negotiation)
- Electronics: 2–4 hrs (test, photograph ports/screen, listing, packaging)
- Luxury watches: 3–5 hrs (detailed photography, authentication, higher-maintenance buyers)

net_hourly_rate = true_net_profit / estimated_time_hrs

━━━ STEP 6 — LISTING STRATEGY & TIPS ━━━
Generate 5 specific, actionable tips for THIS exact item. Be concrete, not generic:
1. PLATFORM CHOICE: Which platform first and why (mention specific reasons for this item type)
2. TITLE STRATEGY: Exact keywords to include in the listing title — what buyers search for
3. PHOTOGRAPHY: Specific angles and detail shots buyers need to see for this item category
4. PRICING STRATEGY: BIN price vs auction, offer enabled yes/no, pricing vs comparable listings
5. TRUST & AUTHENTICITY: How to present the item to maximise buyer confidence (especially if auth_risk is high)

BONUS tips if relevant:
- Timing: day of week / season that maximises sell price for this item
- Condition disclosure: how to describe flaws honestly while still selling effectively

━━━ OUTPUT ━━━
Return ONLY valid JSON (no markdown, no extra text). Replace ALL example numbers with real calculations:
{{
  "buy_price": 0.00,
  "sell_price": 0.00,
  "gross_profit": 0.00,
  "best_platform": "eBay",
  "platform_fee": 0.00,
  "net_profit": 0.00,
  "shipping_cost_est": 10.00,
  "storage_cost_est": 0.00,
  "true_net_profit": 0.00,
  "true_net_profit_after_storage": 0.00,
  "break_even_price": 0.00,
  "roi_percent": 0.00,
  "risk_adjusted_roi": 0.00,
  "minimum_viable_roi": 0.00,
  "capital_at_risk": 0.00,
  "risk_rating": "medium",
  "verdict": "Marginal",
  "recommendation": "Specific actionable recommendation for THIS item — what to do, where, what to watch for, whether it's worth it given the numbers",
  "opportunity_score": 40,
  "liquidity_score": 5,
  "estimated_time_hrs": 2.0,
  "net_hourly_rate": 0.00,
  "listing_tips": [
    "Platform choice: [specific recommendation with reason]",
    "Title: include [specific keywords for this item]",
    "Photos: photograph [specific details for this item type]",
    "Pricing: [specific strategy with numbers]",
    "Trust: [specific auth/trust-building advice]"
  ],
  "platform_breakdown": [
    {{"platform": "eBay",     "fee_pct": {ebay_fee_display}, "fee_amount": 0.00, "net_profit": 0.00, "net_roi": 0.00}},
    {{"platform": "Depop",    "fee_pct": 10.0, "fee_amount": 0.00, "net_profit": 0.00, "net_roi": 0.00}},
    {{"platform": "Poshmark", "fee_pct": 20.0, "fee_amount": 0.00, "net_profit": 0.00, "net_roi": 0.00}},
    {{"platform": "StockX",   "fee_pct": 12.5, "fee_amount": 0.00, "net_profit": 0.00, "net_roi": 0.00}}
  ]
}}

IMPORTANT: If buy_price > sell_price, net_profit IS negative — report it accurately. Do NOT set everything to 0 to avoid showing a bad deal."""

        raw = run_with_search(prompt=prompt, use_search=False, max_tokens=4000, fast=True)
        logger.info(f"Arbitrage raw response (first 300): {raw[:300]}")
        result = parse_first_json(raw)
        if result:
            # Ensure new fields exist for backwards compatibility
            result.setdefault('liquidity_score', 5)
            result.setdefault('estimated_time_hrs', 2.0)
            result.setdefault('storage_cost_est', 0.0)
            result.setdefault('true_net_profit_after_storage', result.get('true_net_profit', 0))
            result.setdefault('risk_adjusted_roi', 0.0)
            result.setdefault('minimum_viable_roi', 0.0)
            result.setdefault('capital_at_risk', result.get('buy_price', 0))
            if result.get('true_net_profit') and result.get('estimated_time_hrs'):
                result.setdefault('net_hourly_rate', round(result['true_net_profit'] / result['estimated_time_hrs'], 2))
            else:
                result.setdefault('net_hourly_rate', 0.0)
            # Ensure every platform_breakdown entry has all fields
            for p in result.get('platform_breakdown', []):
                p.setdefault('net_roi', 0)
                p.setdefault('net_profit', 0)
                p.setdefault('fee_pct', 0)
                p.setdefault('fee_amount', 0)
            return result
        else:
            logger.error(f"Arbitrage: no JSON found. Raw: {raw[:500]}")

    except Exception as e:
        logger.error(f"Arbitrage agent error: {e}")

    ebay_fee_display_safe = round(ebay_fee_pct * 100, 1)
    return {
        "buy_price": 0.00,
        "sell_price": 0.00,
        "gross_profit": 0.00,
        "best_platform": "Unknown",
        "platform_fee": 0.00,
        "net_profit": 0.00,
        "shipping_cost_est": 10.00,
        "storage_cost_est": 0.00,
        "true_net_profit": 0.00,
        "true_net_profit_after_storage": 0.00,
        "break_even_price": 0.00,
        "roi_percent": 0.00,
        "risk_adjusted_roi": 0.00,
        "minimum_viable_roi": 0.00,
        "capital_at_risk": 0.00,
        "risk_rating": "high",
        "verdict": "Avoid",
        "recommendation": "Insufficient data to calculate arbitrage.",
        "opportunity_score": 0,
        "liquidity_score": 0,
        "estimated_time_hrs": 0,
        "net_hourly_rate": 0.00,
        "listing_tips": [],
        "platform_breakdown": [
            {"platform": "eBay",     "fee_pct": ebay_fee_display_safe, "fee_amount": 0, "net_profit": 0, "net_roi": 0},
            {"platform": "Depop",    "fee_pct": 10.0,                  "fee_amount": 0, "net_profit": 0, "net_roi": 0},
            {"platform": "Poshmark", "fee_pct": 20.0,                  "fee_amount": 0, "net_profit": 0, "net_roi": 0},
            {"platform": "StockX",   "fee_pct": 12.5,                  "fee_amount": 0, "net_profit": 0, "net_roi": 0},
        ]
    }
