import logging
from agents.base import run_with_search, parse_first_json

logger = logging.getLogger(__name__)


def research_prices(search_query, product_info):
    """Research sold prices across US platforms."""
    try:
        brand = product_info.get('brand', '')
        product_type = product_info.get('product_type', '')
        era = product_info.get('era', '')
        style = ', '.join(product_info.get('style_descriptors', []))

        is_luxury = brand.lower() in [
            'balenciaga', 'gucci', 'louis vuitton', 'chanel', 'hermes', 'hermès',
            'prada', 'dior', 'fendi', 'givenchy', 'bottega veneta', 'celine',
            'saint laurent', 'ysl', 'valentino', 'versace', 'burberry', 'loewe',
            'off-white', 'rick owens', 'chrome hearts', 'loro piana'
        ]
        luxury_note = "This is a LUXURY brand — check Vestiaire Collective, Fashionphile, Rebag, 1stDibs for realistic resale prices (typically $300–$5000+). Use ONLY completed/sold prices." if is_luxury else ""

        prompt = f"""Research the current US resale market value for: "{search_query}"
Brand: {brand} | Type: {product_type} | Era: {era} | Style: {style}
{luxury_note}

IMPORTANT: Search ONLY for COMPLETED/SOLD transactions — NOT active listings or asking prices. Listed prices are what sellers hope to get; sold prices are what buyers actually paid. These are very different.

Search these sources for SOLD/completed transaction prices:
1. "{search_query} sold eBay USA 2024 2025"
2. "{search_query} sold Poshmark price"
3. "{search_query} Mercari sold listing"
4. "{search_query} StockX last sale"
5. "{search_query} GOAT sold price"
6. "{search_query} Vestiaire Collective sold"
8. "{search_query} Fashionphile price"
9. "{search_query} Rebag resale value"
10. "{search_query} 1stDibs price"
11. "{search_query} Depop sold"
12. "{search_query} resale value 2024 2025"

CRITICAL RULES:
- NEVER output 0 for any price field. Always provide a real number.
- If you cannot find exact live sold listings, use your training knowledge to estimate typical resale prices for this brand and model.
- For luxury brands, estimate based on typical market values you know (e.g. Balenciaga City bag typically $500-$1800 depending on condition/year).
- Set confidence to "low" if estimating, "medium" if found some data, "high" if found multiple recent sales.
- recommended_sell_price: the realistic price a private seller would achieve in a competitive resale market. Set this to 90% of avg_sold (to account for competition, time on market, condition variability), rounded down to nearest $5. NEVER set higher than max_sold.

Return ONLY valid JSON (no markdown, no extra text):
{{
  "currency": "USD",
  "min_sold": 450,
  "max_sold": 1200,
  "avg_sold": 750,
  "recommended_sell_price": 750,
  "confidence": "medium",
  "sources": [
    {{"platform": "eBay", "price": 750, "url": "", "date": "2025-01", "title": "example sold listing"}}
  ],
  "auction_prices": [],
  "market_notes": "brief market commentary based on what you found",
  "price_trend": "rising/stable/falling"
}}

Fill in the numbers above with REAL data from your search. The example numbers shown are placeholders only."""

        raw = run_with_search(prompt=prompt, use_search=True, max_tokens=5000)
        logger.info(f"Pricing raw response (first 200): {raw[:200]}")
        result = parse_first_json(raw)
        if result:
            # If all prices are zero, retry with a knowledge-only prompt
            if not result.get('avg_sold') and not result.get('recommended_sell_price'):
                logger.warning("Pricing returned all zeros — retrying with knowledge-only prompt")
                fallback_prompt = f"""What is the typical resale price range for "{search_query}" in the USA in 2024-2025?
Brand: {brand} | Type: {product_type}

Use your training knowledge about this item's resale market. Give realistic USD prices.

Return ONLY valid JSON:
{{
  "currency": "USD",
  "min_sold": 200,
  "max_sold": 800,
  "avg_sold": 500,
  "recommended_sell_price": 500,
  "confidence": "low",
  "sources": [],
  "auction_prices": [],
  "market_notes": "Estimated from training knowledge — live search unavailable",
  "price_trend": "stable"
}}

Replace the example numbers with your REAL estimates for this item. NEVER output 0."""
                raw2 = run_with_search(prompt=fallback_prompt, use_search=False, max_tokens=1000, fast=True)
                result2 = parse_first_json(raw2)
                if result2 and result2.get('avg_sold') and result2['avg_sold'] > 0:
                    result2['confidence'] = 'low'
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
        "confidence": "low",
        "sources": [],
        "auction_prices": [],
        "market_notes": "Could not retrieve pricing data.",
        "price_trend": "stable"
    }
