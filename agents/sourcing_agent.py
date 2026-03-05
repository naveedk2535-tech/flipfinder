import json
import logging
from agents.base import run_with_search

logger = logging.getLogger(__name__)


def find_sourcing_deals(search_query, avg_sold_price, product_info=None):
    """Find cheapest sourcing deals and similar items."""
    try:
        product_info = product_info or {}
        colors = ', '.join(product_info.get('colors', []))
        style = ', '.join(product_info.get('style_descriptors', []))
        product_type = product_info.get('product_type', '')
        target_buy = round(avg_sold_price * 0.45, 2) if avg_sold_price else 0

        prompt = f"""Find the cheapest places to BUY this item right now: "{search_query}"
Colors: {colors} | Style: {style} | Type: {product_type}
Target buy price: under £{target_buy} (45% of avg sell price £{avg_sold_price})

Search these sources:
1. "{search_query} cheap buy now eBay"
2. "{search_query} Vinted buy low price UK"
3. "{search_query} Facebook Marketplace cheap UK"
4. "{search_query} charity shop online ASOS Marketplace"
5. "{search_query} Depop low price buy now"
6. "{colors} {product_type} similar style cheap"
7. "{style} {product_type} auction lot cheap"
8. "similar to {search_query} alternative cheap"

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
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])

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
