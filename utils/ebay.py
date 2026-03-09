"""eBay Browse API utility for FlipAFind.

Searches active eBay listings using the Browse API (v1).
OAuth client_credentials flow with token caching (2hr expiry).
Graceful fallback: returns [] on any failure.
"""
import base64
import logging
import os
import threading
import time

import requests

logger = logging.getLogger(__name__)

# Credentials — read from environment variables (set in WSGI config)
_APP_ID = os.environ.get('EBAY_APP_ID', '')
_CERT_ID = os.environ.get('EBAY_CERT_ID', '')

# Token cache
_token_lock = threading.Lock()
_cached_token = None
_token_expiry = 0  # epoch seconds


def _get_token() -> str | None:
    """Get a valid OAuth application token, refreshing if expired."""
    global _cached_token, _token_expiry

    if not _APP_ID or not _CERT_ID:
        logger.warning("eBay credentials not configured (EBAY_APP_ID / EBAY_CERT_ID)")
        return None

    with _token_lock:
        if _cached_token and time.time() < _token_expiry - 60:
            return _cached_token

        try:
            creds = base64.b64encode(f"{_APP_ID}:{_CERT_ID}".encode()).decode()
            resp = requests.post(
                'https://api.ebay.com/identity/v1/oauth2/token',
                headers={
                    'Authorization': f'Basic {creds}',
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                data={
                    'grant_type': 'client_credentials',
                    'scope': 'https://api.ebay.com/oauth/api_scope',
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                _cached_token = data['access_token']
                _token_expiry = time.time() + data.get('expires_in', 7200)
                logger.info("eBay OAuth token refreshed")
                return _cached_token
            else:
                logger.warning(f"eBay OAuth failed: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"eBay OAuth error: {e}")

    return None


def search_ebay(query: str, limit: int = 10) -> list[dict]:
    """Search eBay active listings via Browse API.

    Returns list of dicts: {title, price, shipping_cost, total_price,
                            condition, url, image_url, platform}
    Sorted by price ascending. Returns [] on any failure.
    """
    token = _get_token()
    if not token:
        return []

    try:
        # Track API call
        try:
            from utils.api_tracker import record
            record('ebay', 'browse', success=True, quota_hit=False)
        except Exception:
            pass

        resp = requests.get(
            'https://api.ebay.com/buy/browse/v1/item_summary/search',
            headers={
                'Authorization': f'Bearer {token}',
                'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US',
                'Content-Type': 'application/json',
            },
            params={
                'q': query,
                'limit': min(limit, 50),
                'sort': 'price',
            },
            timeout=10,
        )

        if resp.status_code != 200:
            logger.warning(f"eBay Browse API error: {resp.status_code} {resp.text[:200]}")
            return []

        data = resp.json()
        items = data.get('itemSummaries', [])
        results = []

        for item in items[:limit]:
            price_val = 0.0
            if item.get('price'):
                try:
                    price_val = float(item['price'].get('value', 0))
                except (ValueError, TypeError):
                    pass

            shipping_cost = 0.0
            shipping_info = item.get('shippingOptions', [{}])
            if shipping_info:
                ship = shipping_info[0] if isinstance(shipping_info, list) else shipping_info
                ship_cost = ship.get('shippingCost', {})
                if isinstance(ship_cost, dict):
                    try:
                        shipping_cost = float(ship_cost.get('value', 0))
                    except (ValueError, TypeError):
                        pass

            results.append({
                'title': item.get('title', ''),
                'price': price_val,
                'shipping_cost': shipping_cost,
                'total_price': round(price_val + shipping_cost, 2),
                'condition': item.get('condition', ''),
                'url': item.get('itemWebUrl', ''),
                'image_url': (item.get('image', {}) or {}).get('imageUrl', ''),
                'platform': 'eBay',
            })

        results.sort(key=lambda x: x['total_price'])
        logger.info(f"eBay search '{query}': {len(results)} results")
        return results

    except Exception as e:
        logger.warning(f"eBay Browse API error: {e}")
        return []
