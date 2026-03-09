"""Currency conversion utility for FlipAFind.

Converts foreign listing prices to USD using a free API with hardcoded fallback rates.
"""
import logging
import requests

logger = logging.getLogger(__name__)

# Hardcoded fallback rates (approximate, updated Mar 2026)
# These are "1 unit of foreign currency = X USD"
FALLBACK_RATES_TO_USD = {
    'USD': 1.0,
    'GBP': 1.27,
    'EUR': 1.08,
    'CAD': 0.72,
    'AUD': 0.64,
    'JPY': 0.0067,
    'PKR': 0.0036,    # 1 PKR ≈ $0.0036 → 4190 PKR ≈ $15
    'INR': 0.012,
    'CNY': 0.14,
    'KRW': 0.00074,
    'MXN': 0.058,
    'BRL': 0.17,
    'SGD': 0.75,
    'HKD': 0.13,
    'NZD': 0.59,
    'SEK': 0.095,
    'NOK': 0.093,
    'DKK': 0.145,
    'CHF': 1.13,
    'ZAR': 0.054,
    'THB': 0.029,
    'MYR': 0.22,
    'PHP': 0.018,
    'IDR': 0.000063,
    'AED': 0.27,
    'SAR': 0.27,
    'TRY': 0.028,
    'PLN': 0.26,
    'CZK': 0.044,
    'HUF': 0.0028,
    'RUB': 0.011,
    'TWD': 0.031,
    'BDT': 0.0083,
    'LKR': 0.0033,
    'NGN': 0.00063,
    'EGP': 0.020,
    'KES': 0.0077,
}


def _fetch_live_rate(from_currency: str) -> float | None:
    """Try to fetch a live exchange rate from a free API. Returns rate to USD or None."""
    try:
        # Using exchangerate-api.com free tier (no key needed for this endpoint)
        url = f"https://open.er-api.com/v6/latest/{from_currency}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('result') == 'success' and 'USD' in data.get('rates', {}):
                rate = data['rates']['USD']
                logger.info(f"Live rate: 1 {from_currency} = {rate} USD")
                return float(rate)
    except Exception as e:
        logger.warning(f"Live exchange rate fetch failed for {from_currency}: {e}")
    return None


def convert_to_usd(amount: float, from_currency: str) -> tuple[float, str]:
    """Convert an amount from a foreign currency to USD.

    Returns:
        (usd_amount, method) where method is 'live' or 'fallback' or 'none'
    """
    if not amount or amount <= 0:
        return 0.0, 'none'

    from_currency = (from_currency or 'USD').upper().strip()

    if from_currency == 'USD':
        return amount, 'none'

    # Try live rate first
    rate = _fetch_live_rate(from_currency)
    if rate is not None:
        converted = round(amount * rate, 2)
        logger.info(f"Converted {amount} {from_currency} → ${converted} USD (live rate: {rate})")
        return converted, 'live'

    # Fallback to hardcoded rates
    rate = FALLBACK_RATES_TO_USD.get(from_currency)
    if rate is not None:
        converted = round(amount * rate, 2)
        logger.info(f"Converted {amount} {from_currency} → ${converted} USD (fallback rate: {rate})")
        return converted, 'fallback'

    # Unknown currency — log warning and return original (assume USD)
    logger.warning(f"Unknown currency '{from_currency}' — cannot convert {amount}, treating as USD")
    return amount, 'none'
