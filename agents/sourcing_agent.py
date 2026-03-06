import logging
from agents.base import run_with_search, parse_first_json

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

PART 1 — Search for the cheapest current listings:
1. "{search_query} cheap buy now eBay USA"
2. "{search_query} Poshmark low price"
3. "{search_query} Mercari cheap USA"
4. "{search_query} Facebook Marketplace cheap"
5. "{search_query} Depop low price"
6. "{search_query} OfferUp cheap"
7. "{search_query} Amazon used cheap"
8. "{search_query} thrift store goodwill cheap"

PART 2 — Search for SIMILAR items by style/aesthetic that could be flipped too:
9. "similar to {search_query} style alternative resale"
10. "{search_query} alternative Farfetch Net-a-Porter editorialist"
11. "{search_query} similar recommended PurseForum PurseBlog"
12. "{search_query} style similar GOAT StockX alternative"

PART 3 — Find budget-friendly dupes/alternatives at mass-market stores:
13. "{product_type} {style} dupe Walmart Shein affordable"
14. "{search_query} dupe alternative Zara H&M ASOS Target"
15. "{product_type} similar style Amazon Costco under $100"
16. "{style} {product_type} TJ Maxx Burlington Costco budget"

CRITICAL PRICING RULE:
- cheapest_found MUST be the actual cheapest listing price you found on any platform, even if it is above the target buy price. NEVER return 0 for cheapest_found.
- avg_source_price MUST be the average of the listings you found. NEVER return 0.
- If you found listings but they are all above target price, set below_target=false and still fill in cheapest_found with the actual price.
- best_deals should contain the actual cheapest listings found, even if overpriced for arbitrage.

CRITICAL SIMILAR ITEMS: You MUST fill in similar_by_style, similar_by_color, AND budget_alternatives with at least 2 real items each.
- similar_by_style: items with the same aesthetic/silhouette/design language (can include Farfetch, Net-a-Porter, editorialist.com, PurseForum picks, GOAT/StockX alternatives)
- similar_by_color: items with matching or complementary color palette
- budget_alternatives: REAL cheaper versions/dupes from mass-market stores. You MUST return AT LEAST 4 items. MANDATORY: you MUST include one item from EACH of these 4 stores — Shein, Walmart, Amazon, AND Target — every single time. Then optionally add more from Zara, H&M, ASOS, TJ Maxx, Burlington, or Costco. Must be genuinely similar in look/feel/color but significantly cheaper. Include the exact store name and real USD price. These should NOT be resale items.
- Use your training knowledge if search results are insufficient — never leave these arrays empty

Return ONLY valid JSON (no markdown, no extra text):
{{
  "best_deals": [
    {{
      "title": "Real listing title here",
      "platform": "eBay",
      "price": 85,
      "url": "https://real-url.com",
      "condition": "Used - Good",
      "profit_potential": 150,
      "buy_link": "https://real-url.com"
    }}
  ],
  "cheapest_found": 85,
  "avg_source_price": 120,
  "below_target": true,
  "sourcing_notes": "Actionable tips on where and how to source this item",
  "similar_by_style": [
    {{"item": "Real Similar Item Name", "platform": "Farfetch", "price": 200, "why_similar": "Same silhouette and hardware design", "url": ""}},
    {{"item": "Another Real Item", "platform": "PurseForum recommended", "price": 350, "why_similar": "Frequently recommended alongside this model", "url": ""}}
  ],
  "similar_by_color": [
    {{"item": "Real Color-Match Item", "platform": "GOAT", "price": 180, "why_similar": "Same colorway", "url": ""}},
    {{"item": "Real Complementary Item", "platform": "StockX", "price": 220, "why_similar": "Matching color palette", "url": ""}}
  ],
  "budget_alternatives": [
    {{"item": "Woven Crossbody Bag", "store": "Shein", "price": 18, "why_similar": "Similar woven texture and silhouette at a fraction of the price", "url": ""}},
    {{"item": "Structured Mini Tote", "store": "Walmart", "price": 22, "why_similar": "Similar structured design and color palette", "url": ""}},
    {{"item": "Minimalist Shoulder Bag", "store": "Amazon", "price": 35, "why_similar": "Matching color and similar silhouette", "url": ""}},
    {{"item": "Mini Structured Tote", "store": "Target", "price": 28, "why_similar": "Similar minimalist design at a fraction of the cost", "url": ""}}
  ]
}}

Replace ALL placeholder values with REAL items and prices. Arrays must NOT be empty.
IMPORTANT: The "item" field must be the product name ONLY — do NOT prefix it with the store name (e.g. write "Woven Tote Bag", NOT "Shein Woven Tote Bag")."""

        raw = run_with_search(prompt=prompt, use_search=True, max_tokens=6000)
        logger.info(f"Sourcing raw response (first 200): {raw[:200]}")
        result = parse_first_json(raw)
        if result:
            return result
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
        "similar_by_color": [],
        "budget_alternatives": []
    }
