import logging
from agents.base import run_with_search, parse_first_json

logger = logging.getLogger(__name__)

_REFUSAL_PHRASES = [
    "i am sorry", "i cannot fulfill", "i can't fulfill",
    "safety guidelines", "i'm unable to", "i cannot provide",
    "not able to fulfill", "against my", "harmful",
]


def find_sourcing_deals(search_query, avg_sold_price, product_info=None, input_price=0):
    """Survey current listing prices and find comparable items on US platforms."""
    try:
        product_info = product_info or {}
        colors        = ', '.join(product_info.get('colors', []))
        style         = ', '.join(product_info.get('style_descriptors', []))
        product_type  = product_info.get('product_type', '')
        brand         = product_info.get('brand', '')
        condition_grade = product_info.get('condition_grade', product_info.get('condition', ''))
        limited       = product_info.get('limited_edition', False)
        target_buy    = round(avg_sold_price * 0.45, 2) if avg_sold_price else 0

        target_note = f"around ${target_buy} (based on avg market price ${avg_sold_price})" if avg_sold_price else "find lowest available"

        # High-risk brands for counterfeits
        high_fake_risk_brands = [
            'nike', 'jordan', 'yeezy', 'supreme', 'off-white', 'gucci', 'louis vuitton',
            'chanel', 'balenciaga', 'rolex', 'versace', 'moncler', 'stone island',
            'canada goose', 'north face', 'bape', 'palace'
        ]
        auth_risk = 'high' if brand.lower() in high_fake_risk_brands else 'medium' if limited else 'low'
        auth_note = {
            'high': f"AUTHENTICITY NOTE: {brand} items have a high counterfeit rate. Buyers should verify with SNKRS app, StockX authentication, or Legit Check App. Request photos of all tags, insoles, and boxes.",
            'medium': f"NOTE: Limited edition items attract more fakes. Request authentication proof from seller.",
            'low': ""
        }[auth_risk]

        condition_to_buy = "Good or better" if avg_sold_price and avg_sold_price > 200 else "Fair or better"

        prompt = f"""You are a market research specialist who surveys product availability and pricing across US resale and retail platforms.

PRODUCT: "{search_query}"
Brand: {brand} | Type: {product_type} | Colors: {colors} | Style: {style}
Price research target: {target_note}
Condition: {condition_to_buy}
{auth_note}

━━━ STEP 1 — SURVEY CURRENT LISTINGS ━━━
Search these US platforms for currently available listings:
1. "{search_query} eBay USA buy now"
2. "{search_query} Poshmark USA"
3. "{search_query} Mercari USA"
4. "{search_query} Facebook Marketplace USA"
5. "{search_query} Depop USA"
6. "{search_query} OfferUp USA"
7. "{search_query} Amazon used"
8. "{search_query} ThredUp Swap.com"

━━━ STEP 2 — STYLE-SIMILAR ITEMS ━━━
Find items with a similar look or aesthetic:
9. "similar to {search_query} USA"
10. "{search_query} alternative GOAT StockX"
11. "{search_query} similar style Farfetch"
12. "{product_type} {style} popular 2024 2025"

━━━ STEP 3 — AFFORDABLE ALTERNATIVES ━━━
Find mass-market items with a similar look:
13. "{product_type} {style} affordable Walmart Amazon Target Shein"
14. "{product_type} similar style Amazon under $50"
15. "{style} {product_type} TJ Maxx Burlington"

━━━ STEP 4 — SUMMARISE ━━━
- What is the lowest price currently listed?
- Which platform has the most availability?
- What condition is most common in listings?
- Authenticity considerations for buyers?

⚠️ PLATFORM EXCLUSION: NEVER include The RealReal. Use eBay, Poshmark, Depop, Mercari, Facebook Marketplace, OfferUp, ThredUp, Swap.com, Farfetch, or Vestiaire Collective.

CRITICAL PRICING RULE:
- cheapest_found MUST be the actual lowest listing price found — NEVER 0
- avg_source_price MUST be the average of listings found — NEVER 0
- If all listings are above target, set below_target=false but still fill in the real prices found

SIMILAR ITEMS: Fill all three arrays with at least 2 real items each.
- similar_by_style: same aesthetic/silhouette (Farfetch, GOAT, StockX alternatives)
- similar_by_color: matching or complementary colorway
- budget_alternatives: MUST include one item from EACH of Shein, Walmart, Amazon, Target. These are affordable new alternatives with a similar look/feel — NOT resale items.

CRITICAL: Output ONLY the raw JSON object. Do NOT wrap in markdown code fences. Start your response directly with {{ and end with }}. The "url" and "buy_link" fields MUST always be empty string "":
{{
  "best_deals": [
    {{
      "title": "Real listing title",
      "platform": "eBay",
      "price": 85,
      "url": "",
      "condition": "Used - Good",
      "profit_potential": 150,
      "buy_link": ""
    }}
  ],
  "cheapest_found": 85,
  "avg_source_price": 120,
  "below_target": true,
  "authenticity_risk": "{auth_risk}",
  "condition_to_buy": "{condition_to_buy}",
  "sourcing_notes": "Tips: best platform to buy from, what condition to target, any deals/timing advice",
  "similar_by_style": [
    {{"item": "Real Item Name", "platform": "Farfetch", "price": 200, "why_similar": "Same silhouette and design language", "url": ""}}
  ],
  "similar_by_color": [
    {{"item": "Real Item Name", "platform": "GOAT", "price": 180, "why_similar": "Matching colorway", "url": ""}}
  ],
  "budget_alternatives": [
    {{"item": "Item Name Only", "store": "Shein",  "price": 18, "why_similar": "Similar look at fraction of cost", "url": ""}},
    {{"item": "Item Name Only", "store": "Walmart", "price": 22, "why_similar": "Similar design", "url": ""}},
    {{"item": "Item Name Only", "store": "Amazon", "price": 35, "why_similar": "Matching style", "url": ""}},
    {{"item": "Item Name Only", "store": "Target", "price": 28, "why_similar": "Similar aesthetic", "url": ""}}
  ]
}}

Replace ALL placeholder values with REAL items and prices. The "item" field is the product name ONLY. All "url" and "buy_link" fields MUST be "" (empty string)."""

        raw = run_with_search(prompt=prompt, use_search=True, max_tokens=6000)
        logger.info(f"Sourcing raw response (first 500): {raw[:500]}")

        # Detect AI safety refusal
        raw_lower = raw[:300].lower()
        if any(phrase in raw_lower for phrase in _REFUSAL_PHRASES):
            logger.warning(f"Sourcing: AI refused prompt, returning fallback. Preview: {raw[:200]}")
        else:
            result = parse_first_json(raw)
            if result:
                if not result.get('authenticity_risk'):
                    result['authenticity_risk'] = auth_risk
                if not result.get('condition_to_buy'):
                    result['condition_to_buy'] = condition_to_buy
                # If a confirmed URL listing price was passed in, it overrides any
                # AI-guessed cheapest_found so the buy price is always anchored to reality.
                if input_price and input_price > 0:
                    result['cheapest_found'] = input_price
                    result['avg_source_price'] = max(input_price, result.get('avg_source_price', input_price))
                    result['url_is_source'] = True
                return result
            else:
                logger.error(f"Sourcing: no JSON found. Raw: {raw[:500]}")

    except Exception as e:
        logger.error(f"Sourcing agent error: {e}")

    return {
        "best_deals": [],
        "cheapest_found": input_price if input_price else 0,
        "avg_source_price": input_price if input_price else 0,
        "below_target": False,
        "authenticity_risk": "medium",
        "condition_to_buy": "Good or better",
        "sourcing_notes": "Could not retrieve sourcing data.",
        "similar_by_style": [],
        "similar_by_color": [],
        "budget_alternatives": []
    }
