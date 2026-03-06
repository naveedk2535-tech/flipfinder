import logging
from agents.base import run_with_search, parse_first_json

logger = logging.getLogger(__name__)


def extract_product_details(text_input=None, image_base64=None, image_media_type=None, link=None):
    """Extract structured product details from image, text, or URL."""
    try:
        prefix = ""
        if link:
            prefix = f'First use web search to fetch and read this URL: {link}\nThen analyse the product found there.\n\n'

        prompt = prefix + """Analyse this product carefully. Extract every detail including:
brand, product_type, model, colors (as array), condition, size,
era/year, materials, notable_features, style_descriptors (array of style tags
like 'vintage', 'streetwear', 'luxury', 'designer', 'collectible'),
auction_relevance (brief note on whether auction houses like Sotheby's,
Christie's, Heritage Auctions would sell this), and generate an optimal
search_query to find this exact item on resale sites.

Return ONLY a valid JSON object with these exact keys (no markdown, no extra text):
{
  "brand": "",
  "product_type": "",
  "model": "",
  "colors": [],
  "condition": "",
  "size": "",
  "era": "",
  "materials": "",
  "notable_features": "",
  "style_descriptors": [],
  "auction_relevance": "",
  "estimated_retail_price": 0,
  "demand_level": "medium",
  "limited_edition": false,
  "search_query": ""
}

Notes on new fields:
- estimated_retail_price: original MSRP/retail price in USD when the item was new. Use 0 if unknown or if this is a vintage/no-longer-sold item.
- demand_level: "high" (hyped/collectible/waitlisted), "medium" (popular but available), or "low" (niche/slow-moving).
- limited_edition: true if this is a collab, limited drop, numbered edition, or sold-out release; false otherwise.
- search_query: make this specific — include brand, model, key variant/colorway, and condition if relevant (e.g. "Nike Air Jordan 1 Retro High OG University Blue size 10 used")."""

        if text_input and not image_base64:
            prompt = f'Product description: {text_input}\n\n' + prompt

        raw = run_with_search(
            prompt=prompt,
            image_base64=image_base64,
            image_media_type=image_media_type,
            use_search=bool(link),
            max_tokens=1000,
            fast=False  # always use full flash — extraction quality is the foundation of all downstream agents
        )

        result = parse_first_json(raw)
        if result:
            return result

    except Exception as e:
        logger.error(f"Extraction agent error: {e}")

    fallback_query = text_input or 'product'
    return {
        "brand": "Unknown",
        "product_type": "Product",
        "model": "",
        "colors": [],
        "condition": "Unknown",
        "size": "",
        "era": "",
        "materials": "",
        "notable_features": "",
        "style_descriptors": [],
        "auction_relevance": "",
        "estimated_retail_price": 0,
        "demand_level": "medium",
        "limited_edition": False,
        "search_query": fallback_query
    }
