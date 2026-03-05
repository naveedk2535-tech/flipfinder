import json
import logging
from agents.base import run_with_search

logger = logging.getLogger(__name__)


def find_sourcing_deals(search_query, avg_sold_price, product_info=None):
    """Find cheapest sourcing deals on US platforms."""
    try:
        product_info = product_info or {}
        colors = ', '.join(product_info.get('colors', []))
        style = ', '.join(product_info.get('style_descriptors', []))
        product_type = product_info.get('product_type', '')
        target_buy = round(avg_sold_price * 0.45, 2) if avg_sold_price else 0

        target_note = f"under ${target_buy} (45% of avg sell price ${avg_sold_price})" if avg_sold_price else "as cheap as possible"

        prompt = f"""Find the cheapest places to BUY this item right now in the USA: "{search_query}"
Colors: {colors} | Style: {style} | Type: {product_type}
Target buy price: {target_note}

Search ALL of these sources for the best prices:
1. "{search_query} cheap buy now eBay USA"
2. "{search_query} Poshmark low price"
3. "{search_query} Mercari cheap USA"
4. "{search_query} Facebook Marketplace cheap"
5. "{search_query} Depop low price"
6. "{search_query} OfferUp cheap"
7. "{search_query} Vinted cheap"
8. "{search_query} Amazon used cheap"
9. "{search_query} site:amazon.com"
10. "{search_query} Target sale"
11. "{search_query} Walmart clearance cheap"
12. "{search_query} Costco deal"
13. "{search_query} thrift store goodwill cheap"
14. "similar to {search_query} cheap alternative USA"

Return ONLY valid JSON (no markdown, no extra text):
{{
  "best_deals": [
    {{
      "title": "",
      "platform": "",
      "price": 0,
      "url": "",
      "condition": "",
      "profit_potential": 0,
      "buy_link": ""
    }}
  ],
  "cheapest_found": 0,
  "avg_source_price": 0,
  "sourcing_notes": "tips on where to source",
  "similar_by_style": [
    {{"item": "", "platform": "", "price": 0, "why_similar": "", "url": ""}}
  ],
  "similar_by_color": [
    {{"item": "", "platform": "", "price": 0, "why_similar": "", "url": ""}}
  ]
}}"""

        raw = run_with_search(prompt=prompt, use_search=True)
        logger.info(f"Sourcing raw response (first 200): {raw[:200]}")
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
        else:
            logger.error(f"Sourcing: no JSON found. Raw: {raw[:500]}")

    except Exception as e:
        logger.error(f"Sourcing agent error: {e}")

    return {
        "best_deals": [],
        "cheapest_found": 0,
        "avg_source_price": 0,
        "sourcing_notes": "Could not retrieve sourcing data.",
        "similar_by_style": [],
        "similar_by_color": []
    }
