import logging
from agents.base import run_with_search, parse_first_json

logger = logging.getLogger(__name__)


def extract_product_details(text_input=None, image_base64=None, image_media_type=None, link=None):
    """Extract structured product details from image, text, or URL with expert chain-of-thought reasoning."""
    try:
        prefix = ""
        if link:
            prefix = (
                f'First use web search to fetch and read this URL: {link}\n'
                f'IMPORTANT: Find and record the exact asking/sale price shown on that page as "listing_price" in your JSON output. If no price is found, set listing_price to 0.\n'
                f'Then analyse the product found there.\n\n'
            )

        prompt = prefix + """You are a world-class product identification specialist, certified resale appraiser, and authentication expert. Analyse this product with maximum precision — your extraction is the foundation for all downstream pricing and arbitrage calculations.

━━━ STEP 1 — PRECISE IDENTIFICATION ━━━
Identify with expert specificity:
- Exact brand, product line, model name, and variant/colorway (use the official product name, not a description)
- Release year, season/collection, or specific drop date (e.g. "FW2019", "February 2022 collab drop", "2017 Retro")
- All physical details: precise colorway names, materials (full-grain vs corrected-grain leather, hardware metal type), construction method
- Edition type: mainline / collab (with whom?) / sample / player exclusive / numbered / unreleased

━━━ STEP 2 — PACKAGING & PROVENANCE ━━━
Determine what accompanies the item — packaging completeness dramatically affects resale value:
- Sneakers: OG box present? Style number on box matches shoe? Tissue paper, extra laces, lace bag, hang tags, receipt?
- Bags: dust bag, authenticity card, serial number card, hologram sticker, receipt/proof of purchase, outer box, padlock and keys?
- Watches: inner and outer box, papers/warranty card, service history, hang tag, extra links, crown tool?
- Electronics: original box, all original cables/charger, accessories, manuals, warranty card, screen protector?
- Clothing: original tags attached, hang tag, authenticity certificate, care label intact?

━━━ STEP 3 — EXPERT CONDITION GRADING ━━━
Grade using standard resale grades. Apply category-specific criteria:

For SNEAKERS: assess — sole wear pattern and depth, midsole yellowing/oxidation, toe box creasing and severity, heel tab flatness/fraying, tongue shape, lining staining, insole wear, any odour indicators, box condition
For BAGS: assess — leather/material condition (scratches, patina, peeling, corner wear), hardware (tarnishing, scratches, missing pieces), lining (staining, tearing, zip function), straps (cracking, stitching), date code/serial legibility, closure function
For WATCHES: assess — crystal condition (deep scratches, chips), case wear (brushed/polished surfaces, dings), bracelet/strap wear, crown/pusher condition, dial condition (scratches, fading, moisture marks), if movement visible: running/stopped
For ELECTRONICS: assess — screen (scratches, cracks, burn-in, dead pixels), chassis (dents, cracks, missing paint), port/button wear, camera lens, stated or estimated battery health, any water damage indicators
For CLOTHING: assess — fabric integrity (pilling, thinning, holes), seam condition, button/zip function, colour fade, staining (location and severity), alterations, label condition

Grades: Deadstock (DS) | New With Tags (NWT) | Like New (LN) | Excellent (EX) | Very Good (VG) | Good (G) | Fair (F) | Poor (P)

━━━ STEP 4 — MARKET DEMAND SIGNALS ━━━
Assess current market demand:
- Has this item been featured recently by celebrities, athletes, or major influencers?
- Is it a sold-out limited release? Has it ever restocked or been retroed?
- Does this specific size/colour command a size premium or discount vs the average? (e.g. "Size 10 is peak demand for this model", "Red colorway outsells black 3:1 on StockX")
- What is the original retail price (MSRP) in USD?
- Which resale platforms are best suited for THIS item type?

━━━ STEP 5 — COUNTERFEIT RISK ASSESSMENT ━━━
Identify the 3–5 most critical authentication checkpoints specific to this brand and model:
- Sneakers: specific stitching patterns, logo font weight/placement, heel tab texture/pull loop, UPC barcode match, tongue label print quality, insole branding, box label details
- Bags: serial number format and placement (by brand), stitching stitch count per inch, hardware weight/stamping depth, leather smell, date code format validity, lining pattern alignment
- Watches: case back engravings (spelling, depth), movement quality (rotor sound, sweep speed), dial printing sharpness, bracelet clasp stamping, cyclops lens magnification, bezel click quality
- Electronics: IMEI/serial number verification method, software version legitimacy, build quality tells, accessory cable quality

Also flag the overall counterfeit risk level for this brand/item.

━━━ STEP 6 — OPTIMAL SEARCH QUERY ━━━
Generate the single best search query to find this exact item's sold transactions on resale platforms.
Format: [Brand] [Exact Model Name] [Colorway] [Size if known] [Condition Grade]
Make it specific enough to find THIS item, not generic results.

━━━ OUTPUT ━━━
Return ONLY valid JSON (no markdown, no extra text). All fields required:
{
  "brand": "",
  "product_type": "",
  "model": "",
  "colors": [],
  "condition": "",
  "condition_grade": "",
  "size": "",
  "era": "",
  "release_year": "",
  "materials": "",
  "notable_features": "",
  "style_descriptors": [],
  "packaging_completeness": "",
  "counterfeit_risk": "medium",
  "auction_relevance": "",
  "estimated_retail_price": 0,
  "listing_price": 0,
  "demand_level": "medium",
  "limited_edition": false,
  "variant_demand_note": "",
  "authenticity_indicators": "",
  "sell_platform_recommendation": "",
  "search_query": ""
}

Field notes:
- condition: expert description with category-specific details (e.g. "Light toe box creasing, grade B midsole yellowing, clean insole, no sole wear, box present but creased — worn 2–3 times")
- condition_grade: MUST be one of: "Deadstock", "New With Tags", "Like New", "Excellent", "Very Good", "Good", "Fair", "Poor"
- packaging_completeness: exact accessories/packaging present (e.g. "OG box with extra laces and lace bag", "Dust bag only", "No accessories", "Full set: box, papers, all links, hang tag")
- counterfeit_risk: "high" (brand heavily counterfeited, always authenticate before buying), "medium" (some fakes circulate), "low" (rarely targeted by counterfeiters)
- release_year: year or season, e.g. "2019" or "FW2021" or "SS2018"
- sell_platform_recommendation: 1–2 best platforms for SELLING this item (e.g. "StockX for DS — best prices; eBay for worn pairs with full photo set")
- demand_level: "high" (sold out/hyped/waitlisted), "medium" (popular but available), "low" (niche/slow-moving)
- limited_edition: true only if it's a collab, numbered edition, limited drop, or confirmed sold-out release
- variant_demand_note: size/color premium insight (e.g. "Mocha colorway commands 20% premium over Panda; size 9–11 most liquid")
- authenticity_indicators: the 3–5 specific checkpoints buyers MUST verify for this exact brand/model
- search_query: precise and optimised — brand + exact model + colorway + size + condition (e.g. "Nike Air Jordan 1 High OG University Blue size 10 Very Good")"""

        if text_input and not image_base64:
            prompt = f'Product description: {text_input}\n\n' + prompt

        raw = run_with_search(
            prompt=prompt,
            image_base64=image_base64,
            image_media_type=image_media_type,
            use_search=bool(link),
            max_tokens=3000,
            fast=False  # extraction quality is the foundation of all downstream agents
        )
        logger.info(f"Extraction raw response (first 300): {raw[:300]}")
        result = parse_first_json(raw)
        if result:
            # Backwards compatibility: ensure condition_grade exists
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
        "release_year": "",
        "materials": "",
        "notable_features": "",
        "style_descriptors": [],
        "packaging_completeness": "Unknown",
        "counterfeit_risk": "medium",
        "auction_relevance": "",
        "estimated_retail_price": 0,
        "listing_price": 0,
        "demand_level": "medium",
        "limited_edition": False,
        "variant_demand_note": "",
        "authenticity_indicators": "",
        "sell_platform_recommendation": "",
        "search_query": fallback_query
    }
