import json
import logging
from agents.base import run_with_search

logger = logging.getLogger(__name__)


def calculate_arbitrage(pricing_data, sourcing_data):
    """Calculate arbitrage profit with platform breakdown."""
    try:
        prompt = f"""You are an expert resale arbitrage calculator. Analyse this market data
and calculate the complete arbitrage opportunity.

PRICING DATA (what it sells for):
{json.dumps(pricing_data, indent=2)}

SOURCING DATA (what you can buy it for):
{json.dumps(sourcing_data, indent=2)}

Calculate precisely:
- Best buy price = cheapest from sourcing_data
- Best sell price = recommended_sell_price from pricing_data
- Gross profit = sell - buy
- Platform fees: eBay 13.5%, Depop 10%, Vinted 5%, StockX 9.5%
- Net profit after fees for EACH platform
- ROI = (net_profit / buy_price) * 100
- Risk: low (price variance <20%), medium (20-50%), high (>50%)
- Opportunity score 0-100 (combines ROI + confidence + demand signal)
- Verdict: "Strong Flip" (ROI>100%), "Decent Flip" (50-100%),
  "Marginal" (20-50%), "Avoid" (<20%)

Return ONLY valid JSON (no markdown, no extra text):
{{
  "buy_price": 0.00,
  "sell_price": 0.00,
  "gross_profit": 0.00,
  "best_platform": "platform name",
  "platform_fee": 0.00,
  "net_profit": 0.00,
  "roi_percent": 0.00,
  "risk_rating": "low/medium/high",
  "verdict": "Strong Flip/Decent Flip/Marginal/Avoid",
  "recommendation": "specific actionable advice",
  "opportunity_score": 75,
  "platform_breakdown": [
    {{"platform": "eBay",   "fee_pct": 13.5, "fee_amount": 0, "net_profit": 0, "net_roi": 0}},
    {{"platform": "Depop",  "fee_pct": 10,   "fee_amount": 0, "net_profit": 0, "net_roi": 0}},
    {{"platform": "Vinted", "fee_pct": 5,    "fee_amount": 0, "net_profit": 0, "net_roi": 0}},
    {{"platform": "StockX", "fee_pct": 9.5,  "fee_amount": 0, "net_profit": 0, "net_roi": 0}}
  ]
}}"""

        raw = run_with_search(prompt=prompt, use_search=False)
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])

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
            {"platform": "eBay",   "fee_pct": 13.5, "fee_amount": 0, "net_profit": 0, "net_roi": 0},
            {"platform": "Depop",  "fee_pct": 10,   "fee_amount": 0, "net_profit": 0, "net_roi": 0},
            {"platform": "Vinted", "fee_pct": 5,    "fee_amount": 0, "net_profit": 0, "net_roi": 0},
            {"platform": "StockX", "fee_pct": 9.5,  "fee_amount": 0, "net_profit": 0, "net_roi": 0}
        ]
    }
