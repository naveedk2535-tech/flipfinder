"""Lightweight URL scraper for extracting product listing metadata.

Uses requests + regex (no BeautifulSoup dependency).
Extracts title, price, description, condition from common meta tags.
Graceful fallback: returns {} on any failure.
"""
import logging
import re

import requests

logger = logging.getLogger(__name__)

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/131.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'Cache-Control': 'max-age=0',
}


def _extract_meta(html: str, prop: str) -> str:
    """Extract content from <meta property="prop" content="..."> or <meta name="prop" content="...">."""
    patterns = [
        rf'<meta\s+(?:property|name)\s*=\s*["\']?{re.escape(prop)}["\']?\s+content\s*=\s*["\']([^"\']*)["\']',
        rf'<meta\s+content\s*=\s*["\']([^"\']*)["\']?\s+(?:property|name)\s*=\s*["\']?{re.escape(prop)}["\']?',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ''


def _extract_title(html: str) -> str:
    """Extract <title> content."""
    m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
    return m.group(1).strip() if m else ''


def _extract_json_ld_price(html: str) -> tuple[float, str]:
    """Try to extract price and currency from JSON-LD structured data."""
    import json
    price, currency = 0.0, ''
    for m in re.finditer(r'<script[^>]*type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE):
        try:
            data = json.loads(m.group(1))
            # Handle array of JSON-LD objects
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get('@type') == 'Product':
                        data = item
                        break
                else:
                    continue
            if isinstance(data, dict):
                offers = data.get('offers', data)
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                if isinstance(offers, dict):
                    p = offers.get('price', offers.get('lowPrice', 0))
                    c = offers.get('priceCurrency', '')
                    if p:
                        price = float(p)
                        currency = c
                        break
        except (json.JSONDecodeError, ValueError, TypeError, IndexError):
            continue
    return price, currency


def _extract_ebay_condition(html: str) -> str:
    """Extract condition text from eBay listing HTML."""
    # eBay shows condition in a specific span/div
    patterns = [
        r'"conditionDisplayName"\s*:\s*"([^"]+)"',
        r'<span[^>]*class="[^"]*ux-textspans[^"]*"[^>]*>(?:New|Used|Pre-owned|Open box|For parts|Refurbished|New with tags|New without tags|New with defects|Certified)[^<]*</span>',
        r'"condition"\s*:\s*"([^"]+)"',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            text = m.group(1) if m.lastindex else m.group(0)
            # Strip HTML tags
            text = re.sub(r'<[^>]+>', '', text).strip()
            return text
    return ''


def _extract_ebay_item_specifics(html: str) -> dict:
    """Extract item specifics (Brand, Type, etc.) from eBay listing."""
    specifics = {}
    # eBay puts item specifics in structured data or specific divs
    # Look for patterns like "Brand": "Anya Hindmarch"
    for m in re.finditer(r'"name"\s*:\s*"([^"]+)"\s*,\s*"value"\s*:\s*"([^"]+)"', html):
        specifics[m.group(1)] = m.group(2)
    return specifics


def scrape_listing_url(url: str) -> dict:
    """Scrape a product listing URL and return structured metadata.

    Returns dict with available keys:
        title, description, price, currency, condition, item_specifics, raw_text
    Returns {} on any failure.
    """
    try:
        session = requests.Session()
        session.headers.update(_HEADERS)
        resp = session.get(url, timeout=15, allow_redirects=True)
        if resp.status_code != 200:
            logger.warning(f"Scraper: HTTP {resp.status_code} for {url[:80]}")
            return {}

        html = resp.text
        result = {}

        # Title
        og_title = _extract_meta(html, 'og:title')
        page_title = _extract_title(html)
        title = og_title or page_title
        if title:
            # Clean eBay suffix like " | eBay"
            title = re.sub(r'\s*\|\s*eBay\s*$', '', title).strip()
            result['title'] = title

        # Description
        og_desc = _extract_meta(html, 'og:description')
        meta_desc = _extract_meta(html, 'description')
        desc = og_desc or meta_desc
        if desc:
            result['description'] = desc

        # Price from meta tags
        meta_price = _extract_meta(html, 'og:price:amount') or _extract_meta(html, 'product:price:amount')
        meta_currency = _extract_meta(html, 'og:price:currency') or _extract_meta(html, 'product:price:currency')

        # Price from JSON-LD
        ld_price, ld_currency = _extract_json_ld_price(html)

        price = 0.0
        currency = ''
        if meta_price:
            try:
                price = float(meta_price.replace(',', ''))
                currency = meta_currency
            except ValueError:
                pass
        if not price and ld_price:
            price = ld_price
            currency = ld_currency

        if price > 0:
            result['price'] = price
        if currency:
            result['currency'] = currency

        # Condition (eBay-specific)
        if 'ebay' in url.lower():
            condition = _extract_ebay_condition(html)
            if condition:
                result['condition'] = condition
            specifics = _extract_ebay_item_specifics(html)
            if specifics:
                result['item_specifics'] = specifics

        # Extract visible text snippet (first ~2000 chars of meaningful text)
        # Remove scripts, styles, and HTML tags
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        if text:
            result['raw_text'] = text[:2000]

        logger.info(f"Scraper: extracted {list(result.keys())} from {url[:60]}")
        return result

    except requests.Timeout:
        logger.warning(f"Scraper: timeout for {url[:80]}")
    except Exception as e:
        logger.warning(f"Scraper: error for {url[:80]}: {e}")

    return {}
