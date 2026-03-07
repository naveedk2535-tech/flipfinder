import json
import logging
from agents.base import run_with_search, parse_first_json

logger = logging.getLogger(__name__)


def calculate_arbitrage(pricing_data, sourcing_data):
    """Calculate arbitrage profit with full US platform P&L, liquidity score, and hourly rate."""
    try:
        prompt = f"""You are a professional US resale arbitrage analyst. Calculate the complete opportunity from the data below. Show your working before outputting JSON.

PRICING DATA (what it sells for in the USA):
{json.dumps(pricing_data, indent=2)}

SOURCING DATA (what you can buy it for in the USA):
{json.dumps(sourcing_data, indent=2)}

━━━ STEP 1 — SET BASE PRICES ━━━
- buy_price = cheapest_found from sourcing_data
  → If cheapest_found is 0 or missing, use avg_source_price
  → If both are 0, use avg_sold from pricing_data × 0.55 as a conservative estimate
- sell_price = recommended_sell_price from pricing_data
  → SANITY CHECK: must be between min_sold and max_sold. If above max_sold, cap at max_sold. If 0, use avg_sold.
- gross_profit = sell_price - buy_price

━━━ STEP 2 — US PLATFORM FEE BREAKDOWN ━━━
Calculate for each platform using gross_profit and sell_price:
- eBay:     fee = sell_price × 0.1350  (13.5% final value fee)
- Depop:    fee = sell_price × 0.1000  (10% fee)
- Poshmark: fee = sell_price × 0.2000  (20% commission)
- StockX:   fee = sell_price × 0.0950  (9.5% seller fee)
net_profit for each platform = gross_profit - platform_fee

━━━ STEP 3 — SHIPPING & TRUE NET ━━━
Estimate US domestic shipping based on product type (use the product_type in sourcing data if available):
- Sneakers/shoes: $12–$15
- Bags/handbags:  $12–$18
- Clothing:       $6–$10
- Electronics:    $12–$20
- Jewellery/watches: $6–$10
- Default:        $10

best_platform = platform with highest net_profit
true_net_profit = best_platform net_profit - shipping_cost_est
break_even_price = (buy_price + shipping_cost_est) / (1 - best_platform_fee_pct/100), rounded up to 2 decimal places

━━━ STEP 4 — ROI & RISK ━━━
roi_percent = (true_net_profit / buy_price) × 100
  → If buy_price = 0, set roi_percent = 0

risk_rating:
- "low"    if price variance (max_sold - min_sold) / avg_sold < 25%
- "medium" if variance 25–60%
- "high"   if variance > 60% OR authenticity_risk = "high" in sourcing data

opportunity_score (0–100): combines ROI + confidence + demand_level + sell_velocity
- Start at 50
- +20 if roi_percent > 80%
- +10 if roi_percent 40–80%
- -10 if roi_percent < 20%
- +10 if confidence = "high"
- -10 if confidence = "low"
- +10 if sell_velocity_days < 10 (fast seller)
- -10 if sell_velocity_days > 30 (slow seller)
- Cap at 95, floor at 5

verdict:
- "Strong Flip"  if roi_percent > 80%
- "Decent Flip"  if roi_percent 40–80%
- "Marginal"     if roi_percent 15–40%
- "Avoid"        if roi_percent < 15% or true_net_profit negative

━━━ STEP 5 — LIQUIDITY & TIME VALUE ━━━
liquidity_score (1–10): How quickly and reliably will this sell?
- Use sell_velocity_days from pricing_data if available
- 1–3 days = score 9–10; 4–7 days = 7–8; 8–14 days = 5–6; 15–30 days = 3–4; 30+ days = 1–2

estimated_time_hrs: realistic total time for this flip (sourcing + photographing + listing + packing + shipping trip)
- Simple clothing: 1–2 hrs
- Sneakers/bags: 2–3 hrs
- Electronics: 2–4 hrs
- Luxury items: 3–5 hrs

net_hourly_rate = true_net_profit / estimated_time_hrs (round to 2 decimal places)

━━━ STEP 6 — LISTING TIPS ━━━
Generate 4–5 specific, actionable tips for THIS exact item on US platforms:
- Which platform to list on first and why
- Exact keywords to include in the title
- What photos to take (angles, details buyers check)
- Pricing strategy (BIN vs auction, price point)
- Any timing advice (day of week, season)
- Authentication / trust-building advice if authenticity_risk is high

━━━ OUTPUT ━━━
Return ONLY valid JSON (no markdown, no extra text). Replace ALL example numbers with your real calculations:
{{
  "buy_price": 150.00,
  "sell_price": 220.00,
  "gross_profit": 70.00,
  "best_platform": "eBay",
  "platform_fee": 29.70,
  "net_profit": 40.30,
  "shipping_cost_est": 12.00,
  "true_net_profit": 28.30,
  "break_even_price": 188.15,
  "roi_percent": 18.87,
  "risk_rating": "medium",
  "verdict": "Marginal",
  "recommendation": "Specific actionable advice for this exact item — what to do, where to list, what to watch out for",
  "opportunity_score": 42,
  "liquidity_score": 6,
  "estimated_time_hrs": 2.5,
  "net_hourly_rate": 11.32,
  "listing_tips": [
    "List on eBay first with Buy It Now + Best Offer — highest traffic for this category",
    "Title must include: brand, exact model name, colorway, size, condition grade",
    "Photograph: front, back, sole, insole, tongue label, box label, any flaws — buyers need all angles",
    "Price 3–5% below the lowest comparable sold listing to move quickly",
    "If condition is Good or above, mention 'no odour, smoke-free home' in description — buyers value this"
  ],
  "platform_breakdown": [
    {{"platform": "eBay",     "fee_pct": 13.5, "fee_amount": 29.70, "net_profit": 40.30, "net_roi": 26.87}},
    {{"platform": "Depop",    "fee_pct": 10,   "fee_amount": 22.00, "net_profit": 48.00, "net_roi": 32.00}},
    {{"platform": "Poshmark", "fee_pct": 20,   "fee_amount": 44.00, "net_profit": 26.00, "net_roi": 17.33}},
    {{"platform": "StockX",   "fee_pct": 9.5,  "fee_amount": 20.90, "net_profit": 49.10, "net_roi": 32.73}}
  ]
}}

IMPORTANT: If sourcing cheapest_found > sell_price, net_profit will be negative — report this accurately. Do NOT set everything to 0."""

        raw = run_with_search(prompt=prompt, use_search=False, max_tokens=3500, fast=True)
        logger.info(f"Arbitrage raw response (first 300): {raw[:300]}")
        result = parse_first_json(raw)
        if result:
            # Ensure new fields exist for backwards compatibility
            result.setdefault('liquidity_score', 5)
            result.setdefault('estimated_time_hrs', 2.0)
            if result.get('true_net_profit') and result.get('estimated_time_hrs'):
                result.setdefault('net_hourly_rate', round(result['true_net_profit'] / result['estimated_time_hrs'], 2))
            else:
                result.setdefault('net_hourly_rate', 0.0)
            return result
        else:
            logger.error(f"Arbitrage: no JSON found. Raw: {raw[:500]}")

    except Exception as e:
        logger.error(f"Arbitrage agent error: {e}")

    return {
        "buy_price": 0.00,
        "sell_price": 0.00,
        "gross_profit": 0.00,
        "best_platform": "Unknown",
        "platform_fee": 0.00,
        "net_profit": 0.00,
        "shipping_cost_est": 10.00,
        "true_net_profit": 0.00,
        "break_even_price": 0.00,
        "roi_percent": 0.00,
        "risk_rating": "high",
        "verdict": "Avoid",
        "recommendation": "Insufficient data to calculate arbitrage.",
        "opportunity_score": 0,
        "liquidity_score": 0,
        "estimated_time_hrs": 0,
        "net_hourly_rate": 0.00,
        "listing_tips": [],
        "platform_breakdown": [
            {"platform": "eBay",     "fee_pct": 13.5, "fee_amount": 0, "net_profit": 0, "net_roi": 0},
            {"platform": "Depop",    "fee_pct": 10,   "fee_amount": 0, "net_profit": 0, "net_roi": 0},
            {"platform": "Poshmark", "fee_pct": 20,   "fee_amount": 0, "net_profit": 0, "net_roi": 0},
            {"platform": "StockX",   "fee_pct": 9.5,  "fee_amount": 0, "net_profit": 0, "net_roi": 0}
        ]
    }
