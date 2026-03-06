import json
import logging
from agents.base import run_with_search, parse_first_json

logger = logging.getLogger(__name__)


def calculate_arbitrage(pricing_data, sourcing_data):
    """Calculate arbitrage profit with US platform breakdown."""
    try:
        prompt = f"""You are an expert resale arbitrage calculator. Analyse this market data
and calculate the complete arbitrage opportunity. All prices are in USD.

PRICING DATA (what it sells for):
{json.dumps(pricing_data, indent=2)}

SOURCING DATA (what you can buy it for):
{json.dumps(sourcing_data, indent=2)}

Calculate precisely:
- Best buy price = cheapest_found from sourcing_data (use avg_sold from pricing_data if cheapest_found is 0 or missing)
- Best sell price = recommended_sell_price from pricing_data. SANITY CHECK: this value must be between min_sold and max_sold from pricing_data. If it exceeds max_sold, cap it at max_sold. If it is 0, use avg_sold instead.
- Gross profit = sell - buy
- Platform fees: eBay 13.5%, Depop 10%, Poshmark 20%, StockX 9.5%
- Net profit after fees for EACH platform (net_profit = gross_profit - fee_amount)
- shipping_cost_est: estimate realistic US domestic shipping cost based on the product type (shoes/bags ~$12, clothing ~$8, electronics ~$15, jewellery ~$6, default $10)
- true_net_profit = best platform net_profit - shipping_cost_est (this is what the seller actually pockets)
- break_even_price = (buy_price + shipping_cost_est) / (1 - best_platform_fee_pct/100) rounded up to 2dp — minimum sell price to not lose money
- ROI = (true_net_profit / buy_price) * 100 — if buy_price is 0, set ROI to 0
- Risk: low (price variance <20%), medium (20-50%), high (>50%)
- Opportunity score 0-100 (combines ROI + confidence + demand)
- Verdict: "Strong Flip" (ROI>100%), "Decent Flip" (50-100%), "Marginal" (20-50%), "Avoid" (<20% or negative)
- listing_tips: array of 3-5 specific, actionable tips for listing THIS exact item (mention the right keywords, photos to take, when to list, pricing strategy, platforms to prioritise)
- IMPORTANT: If sourcing cheapest_found is higher than sell_price, net_profit will be negative — report this accurately with a negative value. Do NOT set everything to 0.

Return ONLY valid JSON (no markdown, no extra text). Fill ALL values with real calculated numbers:
{{
  "buy_price": 150.00,
  "sell_price": 220.00,
  "gross_profit": 70.00,
  "best_platform": "eBay",
  "platform_fee": 29.70,
  "net_profit": 40.30,
  "shipping_cost_est": 10.00,
  "true_net_profit": 30.30,
  "break_even_price": 185.55,
  "roi_percent": 20.20,
  "risk_rating": "medium",
  "verdict": "Marginal",
  "recommendation": "Specific actionable advice here",
  "opportunity_score": 45,
  "listing_tips": [
    "Use keyword-rich title including brand, model, colourway, and size",
    "Take photos on a clean white background — show soles, tags, and any wear",
    "List on eBay with a Buy It Now price and Best Offer enabled to attract more buyers",
    "Price 5% below the lowest comparable sold listing to sell faster",
    "Mention original packaging/box in the title if included — adds 15-20% value"
  ],
  "platform_breakdown": [
    {{"platform": "eBay",     "fee_pct": 13.5, "fee_amount": 29.70, "net_profit": 40.30, "net_roi": 26.87}},
    {{"platform": "Depop",    "fee_pct": 10,   "fee_amount": 22.00, "net_profit": 48.00, "net_roi": 32.00}},
    {{"platform": "Poshmark", "fee_pct": 20,   "fee_amount": 44.00, "net_profit": 26.00, "net_roi": 17.33}},
    {{"platform": "StockX",   "fee_pct": 9.5,  "fee_amount": 20.90, "net_profit": 49.10, "net_roi": 32.73}}
  ]
}}

Replace all example numbers above with your REAL calculations from the sourcing and pricing data provided."""

        raw = run_with_search(prompt=prompt, use_search=False, max_tokens=2000, fast=True)
        result = parse_first_json(raw)
        if result:
            return result

    except Exception as e:
        logger.error(f"Arbitrage agent error: {e}")

    return {
        "buy_price": 0.00,
        "sell_price": 0.00,
        "gross_profit": 0.00,
        "best_platform": "Unknown",
        "platform_fee": 0.00,
        "net_profit": 0.00,
        "roi_percent": 0.00,
        "risk_rating": "high",
        "verdict": "Avoid",
        "recommendation": "Insufficient data to calculate arbitrage.",
        "opportunity_score": 0,
        "platform_breakdown": [
            {"platform": "eBay",     "fee_pct": 13.5, "fee_amount": 0, "net_profit": 0, "net_roi": 0},
            {"platform": "Depop",    "fee_pct": 10,   "fee_amount": 0, "net_profit": 0, "net_roi": 0},
            {"platform": "Poshmark", "fee_pct": 20,   "fee_amount": 0, "net_profit": 0, "net_roi": 0},
            {"platform": "StockX",   "fee_pct": 9.5,  "fee_amount": 0, "net_profit": 0, "net_roi": 0}
        ]
    }
