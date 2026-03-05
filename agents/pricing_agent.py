import json
import logging
from agents.base import run_with_search

logger = logging.getLogger(__name__)


def research_prices(search_query, product_info):
    """Research sold prices across multiple platforms."""
    try:
        brand = product_info.get('brand', '')
        product_type = product_info.get('product_type', '')
        era = product_info.get('era', '')
        style = ', '.join(product_info.get('style_descriptors', []))

        prompt = f"""Search for recent SOLD listings and auction results for: "{search_query}"
Brand: {brand} | Type: {product_type} | Era: {era} | Style: {style}

Perform these searches in order:
1. "{search_query} sold eBay 2024 2025"
2. "{search_query} sold Depop price"
3. "{search_query} Vinted sold price UK"
4. "{search_query} StockX last sale price"
5. "{search_query} auction result Sotheby Christie Heritage"
6. "{search_query} bidding forum sold price"

Find ACTUAL completed sales, not just listings. Extract real transaction prices.

Return ONLY valid JSON (no markdown, no extra text):
{{
  "currency": "GBP",
  "min_sold": 0,
  "max_sold": 0,
  "avg_sold": 0,
  "recommended_sell_price": 0,
  "confidence": "low/medium/high",
  "sources": [
    {{"platform": "eBay", "price": 0, "url": "", "date": "2024-01", "title": ""}}
  ],
  "auction_prices": [
    {{"house": "Sotheby's", "price": 0, "date": "", "lot_description": ""}}
  ],
  "market_notes": "brief market commentary",
  "price_trend": "rising/stable/falling"
}}"""

        raw = run_with_search(prompt=prompt, use_search=True)
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])

    except Exception as e:
        logger.error(f"Pricing agent error: {e}")

    return {
        "currency": "GBP",
        "min_sold": 0,
        "max_sold": 0,
        "avg_sold": 0,
        "recommended_sell_price": 0,
        "confidence": "low",
        "sources": [],
        "auction_prices": [],
        "market_notes": "Could not retrieve pricing data.",
        "price_trend": "stable"
    }
