import logging
from agents.base import run_with_search, parse_first_json

logger = logging.getLogger(__name__)


def extract_product_details(text_input=None, image_base64=None, image_media_type=None, link=None):
    """Extract structured product details from image, text, or URL with chain-of-thought reasoning."""
    try:
        prefix = ""
        if link:
            prefix = (
                f'First use web search to fetch and read this URL: {link}\n'
                f'IMPORTANT: Find and record the exact asking/sale price shown on that page as "listing_price" in your JSON output (e.g. the price the seller is asking, in USD). If no price is found, set listing_price to 0.\n'
                f'Then analyse the product found there.\n\n'
            )

        prompt = prefix + """You are an expert product identification specialist for the US resale market. Follow this process carefully.

━━━ STEP 1 — IDENTIFY ━━━
Look at this product carefully. Identify:
- The exact brand, product line, model name, and variant/colorway
- The specific era or release year if detectable
- All physical characteristics: colors, materials, hardware, markings, labels

━━━ STEP 2 — CONDITION ASSESSMENT ━━━
Grade the condition using these standard US resale grades:
- Deadstock (DS): Brand new, unworn/unused, original packaging intact
- New With Tags (NWT): New, tags attached, never used
- Like New (LN): Used once or twice, no visible flaws
- Excellent (EX): Light use, no significant flaws, minimal signs of wear
- Very Good (VG): Used, minor flaws that don't affect function or appearance significantly
- Good (G): Clearly used, visible wear, some flaws but fully functional
- Fair (F): Heavy wear, notable flaws, still usable
- Poor (P): Major damage or heavy wear

━━━ STEP 3 — MARKET CONTEXT ━━━
Consider for the US resale market:
- Is this item currently in demand? Is it a limited edition, collab, or hyped release?
- Does the specific size/variant command a premium? (e.g. half sizes, collab colorways, rare sizes)
- What is the rough original retail price in USD?
- Which US resale platforms would handle this item best?

━━━ STEP 4 — SEARCH QUERY ━━━
Generate the optimal search query to find this exact item on US resale platforms.
Include: brand + model + key variant/colorway + size (if known) + condition grade

━━━ OUTPUT ━━━
Return ONLY a valid JSON object with these exact keys (no markdown, no extra text):
{
  "brand": "",
  "product_type": "",
  "model": "",
  "colors": [],
  "condition": "",
  "condition_grade": "",
  "size": "",
  "era": "",
  "materials": "",
  "notable_features": "",
  "style_descriptors": [],
  "auction_relevance": "",
  "estimated_retail_price": 0,
  "listing_price": 0,
  "demand_level": "medium",
  "limited_edition": false,
  "variant_demand_note": "",
  "authenticity_indicators": "",
  "search_query": ""
}

Field notes:
- condition: free-text description of what you observe (e.g. "lightly worn, minor creasing on toe box")
- condition_grade: MUST be one of: "Deadstock", "New With Tags", "Like New", "Excellent", "Very Good", "Good", "Fair", "Poor"
- estimated_retail_price: original MSRP in USD when new. Use 0 if unknown or vintage/discontinued.
- listing_price: the actual asking/sale price from the submitted URL. Use 0 if no URL was provided or price could not be found.
- demand_level: "high" (hyped/collectible/waitlisted), "medium" (popular but available), "low" (niche/slow-moving)
- limited_edition: true if collab, limited drop, numbered edition, or sold-out release
- variant_demand_note: note if this specific size/color/variant commands a premium or is rare (e.g. "Size 9.5 in this colorway is the most sought-after" or "Standard colorway, no size premium")
- authenticity_indicators: what to look for to verify this is authentic (key authentication points buyers check)
- search_query: specific — include brand, model, variant/colorway, size, condition grade (e.g. "Nike Air Jordan 1 Retro High OG University Blue size 10 Good condition")"""

        if text_input and not image_base64:
            prompt = f'Product description: {text_input}\n\n' + prompt

        raw = run_with_search(
            prompt=prompt,
            image_base64=image_base64,
            image_media_type=image_media_type,
            use_search=bool(link),
            max_tokens=2500,
            fast=False  # extraction quality is the foundation of all downstream agents
        )
        logger.info(f"Extraction raw response (first 300): {raw[:300]}")
        result = parse_first_json(raw)
        if result:
            # Ensure condition_grade exists for backwards compatibility
            if not result.get('condition_grade'):
                result['condition_grade'] = result.get('condition', 'Good')
            return result
        else:
            logger.error(f"Extraction: no JSON found. Raw: {raw[:500]}")

    except Exception as e:
        logger.error(f"Extraction agent error: {e}")

    fallback_query = text_input or link or 'product'
    return {
        "brand": "Unknown",
        "product_type": "Product",
        "model": "",
        "colors": [],
        "condition": "Unknown",
        "condition_grade": "Good",
        "size": "",
        "era": "",
        "materials": "",
        "notable_features": "",
        "style_descriptors": [],
        "auction_relevance": "",
        "estimated_retail_price": 0,
        "demand_level": "medium",
        "limited_edition": False,
        "variant_demand_note": "",
        "authenticity_indicators": "",
        "search_query": fallback_query
    }
