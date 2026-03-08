import logging
from agents.base import run_with_search, parse_first_json

logger = logging.getLogger(__name__)

_REFUSAL_PHRASES = [
    "i am sorry", "i cannot fulfill", "i can't fulfill",
    "safety guidelines", "i'm unable to", "i cannot provide",
    "not able to fulfill", "against my", "harmful",
]


def _get_category_sourcing_config(product_type: str, brand: str, avg_sold_price: float):
    """Return category-specific sourcing targets, platform priorities, and buy margin guidance."""
    pt = product_type.lower()

    if any(k in pt for k in ['sneaker', 'shoe', 'trainer', 'boot', 'sandal']):
        # Sneakers: huge DS premium on StockX/GOAT; buy DS if margin works, else buy VG for eBay/Depop
        target_pct = 0.48 if avg_sold_price > 300 else 0.42
        buy_platforms = ["eBay Sneakers", "GOAT seller market", "Depop", "StockX (check bid prices)", "Poshmark", "Mercari"]
        condition_to_buy = "Deadstock (for StockX) or Very Good minimum (for eBay/Depop)"
        category_searches = [
            f'"{product_type} {brand}" buy eBay sneakers USA listing',
            f'"{product_type} {brand}" GOAT seller listing price',
            f'"{product_type} {brand}" Depop for sale',
            f'"{product_type} {brand}" StockX ask price',
            f'"{product_type} {brand}" Poshmark for sale',
            f'"{product_type} {brand}" Mercari USA for sale',
            f'"{product_type} {brand}" Facebook Marketplace USA',
            f'"{product_type} {brand}" OfferUp for sale',
        ]
        timing_advice = "eBay auction end times: Sunday 6–9pm EST = highest bids + most buying activity. Best bargains on eBay: Monday–Wednesday when fewer watchers. GOAT seller prices fluctuate daily — check multiple times before buying."
        negotiation = "Poshmark: always send an offer 15–20% below ask. FB Marketplace and OfferUp: always negotiate, sellers expect it. eBay BIN: check 'Make Offer' button — most sellers accept 10–15% below ask."

    elif any(k in pt for k in ['bag', 'handbag', 'purse', 'wallet', 'backpack', 'tote', 'clutch']):
        # Bags: provenance dramatically affects value; authenticity is paramount
        target_pct = 0.55 if avg_sold_price > 500 else 0.50
        buy_platforms = ["Vestiaire Collective", "Poshmark", "Depop", "eBay", "Facebook Marketplace", "Mercari"]
        condition_to_buy = "Excellent or better — hardware and lining condition is critical for resale"
        category_searches = [
            f'"{product_type} {brand}" Vestiaire Collective for sale',
            f'"{product_type} {brand}" Poshmark for sale 2024 2025',
            f'"{product_type} {brand}" eBay USA buy now listing',
            f'"{product_type} {brand}" Depop for sale',
            f'"{product_type} {brand}" Mercari USA',
            f'"{product_type} {brand}" Facebook Marketplace USA',
            f'"{product_type} {brand}" pre-owned buy USA listing',
            f'"{product_type} {brand}" used for sale authentication',
        ]
        timing_advice = "Luxury bags: best deals appear post-holiday season (January) and in summer (July). Estate sales and consignment shops are excellent sources. Authentication upfront saves costly mistakes."
        negotiation = "Vestiaire: offers accepted on most listings — try 10–15% below. Poshmark: low-ball offers often work on older listings (30+ days). eBay BIN: contact seller before buying to negotiate."

    elif 'watch' in pt:
        # Watches: full set is everything; buying no-box requires pricing accordingly
        target_pct = 0.60 if avg_sold_price > 1000 else 0.55
        buy_platforms = ["Chrono24", "WatchFinder", "eBay Watches", "WatchBox", "Bob's Watches", "Facebook watch groups"]
        condition_to_buy = "Excellent or better; full set (box + papers) preferred — commands significant premium on resale"
        category_searches = [
            f'"{product_type} {brand}" Chrono24 for sale listing',
            f'"{product_type} {brand}" eBay USA watches buy now',
            f'"{product_type} {brand}" WatchFinder listing',
            f'"{product_type} {brand}" WatchBox buy',
            f'"{product_type} {brand}" for sale pre-owned watch USA',
            f'"{product_type} {brand}" Facebook watch group for sale',
            f'"{product_type} {brand}" no box price discount',
            f'"{product_type} {brand}" full set box papers asking price',
        ]
        timing_advice = "Watches: best buying opportunities in Q1 (post-Christmas sales, people selling gifts) and Q3. Chrono24 sellers often negotiate 5–10% privately. Grey market prices fluctuate with currency and factory allocations."
        negotiation = "Chrono24: message sellers directly to negotiate, especially on older listings. eBay watch auctions ending late Sunday EST often go cheaper. Always request service history documentation."

    elif any(k in pt for k in ['phone', 'laptop', 'tablet', 'console', 'electronic', 'camera', 'headphone', 'airpod', 'ipad', 'iphone', 'macbook', 'playstation', 'xbox']):
        # Electronics: depreciate fast; buy only in excellent condition or DS
        target_pct = 0.45
        buy_platforms = ["Swappa", "eBay", "Back Market", "Facebook Marketplace", "OfferUp", "Mercari"]
        condition_to_buy = "Excellent minimum for phones/tablets; Good acceptable for consoles/accessories if priced right"
        category_searches = [
            f'"{product_type} {brand}" Swappa for sale listing',
            f'"{product_type} {brand}" eBay USA buy now listing',
            f'"{product_type} {brand}" Back Market refurbished price',
            f'"{product_type} {brand}" Facebook Marketplace USA buy',
            f'"{product_type} {brand}" OfferUp listing price',
            f'"{product_type} {brand}" Mercari USA listing',
            f'"{product_type} {brand}" Craigslist USA for sale',
            f'"{product_type} {brand}" used price USA local deal',
        ]
        timing_advice = "Electronics: buy 2–4 weeks after a new model launch (prices crater when upgrade cycle hits). Best deals: post-holiday January. Facebook Marketplace and OfferUp are best for local deals — no shipping risk."
        negotiation = "Facebook Marketplace: always negotiate, cash offers accepted. Swappa: some sellers flexible but prices are already competitive. eBay: check completed listings to know actual value before offering."

    else:
        # Default / clothing
        target_pct = 0.45
        buy_platforms = ["eBay", "Poshmark", "Depop", "Mercari", "ThredUp", "Facebook Marketplace"]
        condition_to_buy = "Good or better"
        category_searches = [
            f'"{product_type} {brand}" eBay USA buy now',
            f'"{product_type} {brand}" Poshmark USA',
            f'"{product_type} {brand}" Mercari USA',
            f'"{product_type} {brand}" Facebook Marketplace USA',
            f'"{product_type} {brand}" Depop USA',
            f'"{product_type} {brand}" OfferUp USA',
            f'"{product_type} {brand}" ThredUp Swap.com',
            f'"{product_type} {brand}" Amazon used',
        ]
        timing_advice = "Clothing: end-of-season sales create buying opportunities (August for summer, February for winter). ThredUp and Swap.com often have stock at 30–50% below Poshmark prices."
        negotiation = "Poshmark: bundle items for better rates. eBay Make Offer: typically accepted at 10–15% below BIN. Facebook Marketplace: always negotiate, sellers price high expecting offers."

    target_buy = round(avg_sold_price * target_pct, 2) if avg_sold_price else 0
    return {
        'target_buy': target_buy,
        'target_pct': target_pct,
        'buy_platforms': buy_platforms,
        'condition_to_buy': condition_to_buy,
        'category_searches': category_searches,
        'timing_advice': timing_advice,
        'negotiation': negotiation,
    }


def find_sourcing_deals(search_query, avg_sold_price, product_info=None, input_price=0):
    """Survey current listing prices and find sourcing opportunities with category-specific strategy."""
    try:
        product_info  = product_info or {}
        colors        = ', '.join(product_info.get('colors', []))
        style         = ', '.join(product_info.get('style_descriptors', []))
        product_type  = product_info.get('product_type', '')
        brand         = product_info.get('brand', '')
        condition_grade = product_info.get('condition_grade', product_info.get('condition', ''))
        limited       = product_info.get('limited_edition', False)
        packaging     = product_info.get('packaging_completeness', '')

        cfg = _get_category_sourcing_config(product_type, brand, avg_sold_price)
        target_buy     = cfg['target_buy']
        condition_to_buy = cfg['condition_to_buy']
        timing_advice  = cfg['timing_advice']
        negotiation    = cfg['negotiation']

        target_note = (
            f"Target buy price: ${target_buy} ({int(cfg['target_pct']*100)}% of avg market ${avg_sold_price}) — "
            f"this leaves room for fees, shipping, and profit margin"
        ) if avg_sold_price else "find the lowest available price"

        # High-risk brands for counterfeits
        high_fake_risk_brands = [
            'nike', 'jordan', 'yeezy', 'supreme', 'off-white', 'gucci', 'louis vuitton',
            'chanel', 'balenciaga', 'rolex', 'versace', 'moncler', 'stone island',
            'canada goose', 'north face', 'bape', 'palace', 'dior', 'prada', 'hermes',
            'fendi', 'burberry', 'adidas yeezy', 'travis scott', 'sacai'
        ]
        auth_risk = 'high' if brand.lower() in high_fake_risk_brands else 'high' if limited else 'medium'
        auth_note = {
            'high': f"⚠️ HIGH COUNTERFEIT RISK: {brand} items are heavily faked. REQUIRE: photos of all authentication points, tags, serial numbers. Recommend Legit Check App, StockX authentication, or professional auth service before purchase. Budget $15–30 for authentication.",
            'medium': f"MODERATE RISK: Limited/branded items attract some fakes. Request detailed photos of key authentication markers.",
        }.get(auth_risk, "")

        packaging_note = f"\nItem packaging: {packaging} — factor completeness into condition-to-buy assessment." if packaging else ""

        prompt = f"""You are a professional sourcing specialist who finds the best buying opportunities across US resale and retail platforms.

PRODUCT: "{search_query}"
Brand: {brand} | Type: {product_type} | Colors: {colors} | Style: {style}
{target_note}
Condition required: {condition_to_buy}
{auth_note}{packaging_note}

━━━ STEP 1 — SURVEY CURRENT BUY LISTINGS ━━━
Search these platforms for currently available listings at or below target:
1. {cfg['category_searches'][0]}
2. {cfg['category_searches'][1]}
3. {cfg['category_searches'][2]}
4. {cfg['category_searches'][3]}
5. {cfg['category_searches'][4]}
6. {cfg['category_searches'][5]}
7. {cfg['category_searches'][6]}
8. {cfg['category_searches'][7]}

━━━ STEP 2 — STYLE-SIMILAR ALTERNATIVES ━━━
Find items with a similar look/aesthetic — useful for buyers who want the vibe at a different price point:
9.  "similar to {search_query} USA resale"
10. "{product_type} {style} alternative GOAT StockX Farfetch"
11. "{product_type} {colors} {brand} similar style"
12. "{product_type} {style} trending 2024 2025 popular"

━━━ STEP 3 — BUDGET ALTERNATIVES ━━━
Find mass-market items that capture a similar aesthetic at lower cost:
13. "{product_type} {style} Amazon under $60"
14. "{product_type} similar {colors} Target Walmart affordable"
15. "{product_type} {style} Shein ASOS Amazon dupe"

━━━ STEP 4 — SOURCING STRATEGY SUMMARY ━━━
Evaluate:
- What is the lowest price currently listed? On which platform?
- Which platform has the best stock of this item right now?
- What condition dominates the current listings?
- Is the market oversupplied (easy to buy) or undersupplied (hard to find)?
- Best timing advice: {timing_advice}
- Negotiation tips: {negotiation}

⚠️ PLATFORM EXCLUSION: NEVER include The RealReal in any results.

CRITICAL PRICING RULES:
- cheapest_found MUST be the real lowest listing price found — NEVER 0
- avg_source_price MUST be the real average of listings found — NEVER 0
- If all listings exceed target, set below_target=false but still report real prices
- If no listings found, estimate based on market knowledge and set url_is_source=false

CRITICAL: Output ONLY the raw JSON object. No markdown. Start directly with {{ end with }}. All "url" and "buy_link" fields MUST always be "":
{{
  "best_deals": [
    {{
      "title": "Exact listing title",
      "platform": "eBay",
      "price": 0,
      "url": "",
      "condition": "Used - Good",
      "profit_potential": 0,
      "buy_link": ""
    }}
  ],
  "cheapest_found": 0,
  "avg_source_price": 0,
  "below_target": false,
  "authenticity_risk": "{auth_risk}",
  "condition_to_buy": "{condition_to_buy}",
  "sourcing_notes": "Platform-specific insights: which platform has the best stock, what condition to target, any negotiation opportunities",
  "buy_strategy": {{
    "recommended_platform": "eBay",
    "target_condition": "{condition_to_buy}",
    "timing_advice": "{timing_advice}",
    "negotiation_tips": "{negotiation}",
    "red_flags": "What to avoid: signs of a bad deal, overpriced listings, suspicious sellers"
  }},
  "auth_checklist": [
    "Authentication step 1 specific to this brand/item",
    "Authentication step 2",
    "Authentication step 3"
  ],
  "similar_by_style": [
    {{"item": "Real Item Name", "platform": "Farfetch", "price": 0, "why_similar": "Same silhouette and design language", "url": ""}}
  ],
  "similar_by_color": [
    {{"item": "Real Item Name", "platform": "GOAT", "price": 0, "why_similar": "Matching colorway", "url": ""}}
  ],
  "budget_alternatives": [
    {{"item": "Item Name Only", "store": "Amazon", "price": 0, "why_similar": "Similar look at fraction of cost", "url": ""}},
    {{"item": "Item Name Only", "store": "Shein",  "price": 0, "why_similar": "Similar design aesthetic", "url": ""}},
    {{"item": "Item Name Only", "store": "Walmart", "price": 0, "why_similar": "Similar design", "url": ""}},
    {{"item": "Item Name Only", "store": "Target",  "price": 0, "why_similar": "Similar aesthetic", "url": ""}}
  ]
}}

Replace ALL zeros with REAL prices. All "url" and "buy_link" fields MUST be empty string "". The "item" field is product name ONLY (no stores)."""

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
                # If a confirmed URL listing price was passed in, anchor to it
                if input_price and input_price > 0:
                    result['cheapest_found'] = input_price
                    result['avg_source_price'] = max(input_price, result.get('avg_source_price', input_price))
                    result['url_is_source'] = True
                # Populate buy_strategy defaults if AI omitted it
                if not result.get('buy_strategy'):
                    result['buy_strategy'] = {
                        'recommended_platform': 'eBay',
                        'target_condition': condition_to_buy,
                        'timing_advice': timing_advice,
                        'negotiation_tips': negotiation,
                        'red_flags': 'Verify seller feedback, request multiple photos, avoid listings without condition details',
                    }
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
        "buy_strategy": {
            "recommended_platform": "eBay",
            "target_condition": "Good or better",
            "timing_advice": "Check eBay completed listings for realistic pricing.",
            "negotiation_tips": "Send best offer on eBay BIN listings.",
            "red_flags": "Avoid listings with no photos or vague condition descriptions.",
        },
        "auth_checklist": [],
        "similar_by_style": [],
        "similar_by_color": [],
        "budget_alternatives": [],
    }
