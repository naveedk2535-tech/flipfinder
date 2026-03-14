import os
import uuid
import base64
import json
import io
from datetime import datetime, timedelta
from threading import Thread
from PIL import Image as PilImage
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app import db, limiter
from models.analysis import Analysis
from agents.extraction_agent import extract_product_details
from agents.pricing_agent import research_prices
from agents.sourcing_agent import find_sourcing_deals
from agents.arbitrage_agent import calculate_arbitrage
from agents.trends_agent import get_trend_data, get_social_data
from utils.currency import convert_to_usd
from utils.ebay import search_ebay
from urllib.parse import quote_plus
import logging
import re
import requests

logger = logging.getLogger(__name__)

analysis_bp = Blueprint('analysis', __name__, url_prefix='/analyse')

# SerpAPI keys for Google Shopping
_SERPAPI_KEYS = [k for k in [
    os.environ.get("SERPAPI_KEY"),
    os.environ.get("SERPAPI_KEY_2"),
] if k]


def _search_google_shopping(query: str, limit: int = 8) -> list[dict]:
    """Search Google Shopping via SerpAPI for real buy prices.
    Returns list of {title, price, platform, url, image_url, condition}."""
    if not _SERPAPI_KEYS:
        return []
    results = []
    for key in _SERPAPI_KEYS:
        try:
            resp = requests.get(
                'https://serpapi.com/search.json',
                params={
                    'engine': 'google_shopping',
                    'q': query,
                    'api_key': key,
                    'num': limit,
                    'gl': 'us',
                    'hl': 'en',
                },
                timeout=10,
            )
            if resp.status_code == 429:
                continue  # try next key
            if resp.status_code != 200:
                logger.warning(f"Google Shopping API error: {resp.status_code}")
                continue
            data = resp.json()
            for item in data.get('shopping_results', [])[:limit]:
                price_str = item.get('extracted_price') or item.get('price', '')
                price_val = 0.0
                if isinstance(price_str, (int, float)):
                    price_val = float(price_str)
                elif isinstance(price_str, str):
                    m = re.search(r'[\d,]+\.?\d*', price_str.replace(',', ''))
                    if m:
                        try:
                            price_val = float(m.group())
                        except ValueError:
                            pass
                results.append({
                    'title': item.get('title', ''),
                    'price': price_val,
                    'shipping_cost': 0,
                    'total_price': price_val,
                    'condition': item.get('second_hand_condition', 'New'),
                    'url': item.get('product_link', '') or item.get('link', ''),
                    'image_url': item.get('thumbnail', ''),
                    'platform': item.get('source', 'Google Shopping'),
                })
            # Track API call
            try:
                from utils.api_tracker import record
                record('serpapi', 'google_shopping', success=True, quota_hit=False)
            except Exception:
                pass
            break  # success, don't try next key
        except Exception as e:
            logger.warning(f"Google Shopping search error: {e}")
            continue
    # Sort by price ascending, filter out $0 items
    results = [r for r in results if r['price'] > 0]
    results.sort(key=lambda x: x['total_price'])
    return results

# Platform fee rates for sell link net-profit estimates
_PLATFORM_FEES = {
    'eBay': 0.1335,
    'StockX': 0.125,
    'Depop': 0.10,
    'Poshmark': 0.20,
    'Mercari': 0.10,
    'Grailed': 0.119,
    'Swappa': 0.03,        # 3% seller fee
    'Back Market': 0.10,   # ~10% commission
    'Chrono24': 0.065,     # 6.5% seller fee
    'Vestiaire Collective': 0.12,  # ~12% commission
    'Fashionphile': 0.15,  # ~15% consignment (varies by item value)
    'Rebag': 0.15,         # ~15% consignment
    "Sotheby's": 0.20,     # ~20% buyer's premium (seller pays less, but effective ~15-20%)
    'Heritage Auctions': 0.20,  # ~20% buyer's premium
    "Christie's": 0.20,    # ~20% buyer's premium
    'Facebook Marketplace': 0.05,  # 5% for shipped items (0% local pickup, but most resellers ship)
    'OfferUp':   0.129,    # 12.9% for shipped items (0% local pickup)
    'Chairish':  0.20,     # ~20% consignment (furniture/decor)
}

# Grailed-eligible categories
_GRAILED_CATEGORIES = {'sneaker', 'shoe', 'clothing', 'apparel', 'jacket', 'hoodie',
                       'shirt', 'pants', 'streetwear', 'dress', 'coat', 'jeans'}


def _generate_sell_links(query: str, product_type: str, sell_price: float) -> list[dict]:
    """Generate platform search URLs with fee/net estimates.
    Category-aware: only shows platforms relevant to the product type."""
    q = quote_plus(query)
    pt = product_type.lower() if product_type else ''

    # Determine category for platform filtering
    is_electronics = any(k in pt for k in ['phone', 'laptop', 'tablet', 'console', 'electronic',
                                            'camera', 'headphone', 'smartphone', 'computer', 'gaming'])
    is_watch = 'watch' in pt
    is_fashion = any(k in pt for k in _GRAILED_CATEGORIES) or any(
        k in pt for k in ['bag', 'handbag', 'purse', 'wallet', 'backpack', 'tote'])

    # Universal platforms — work for all categories
    platforms = [
        {'platform': 'eBay',             'url': f'https://www.ebay.com/sch/i.html?_nkw={q}'},
        {'platform': 'Mercari',          'url': f'https://www.mercari.com/search/?keyword={q}'},
    ]

    # Facebook Marketplace & OfferUp — local pickup only, no authentication or buyer protection.
    # Only relevant for electronics, furniture, collectibles, general items.
    # Not relevant for sneakers (StockX/GOAT), luxury bags (consignment), watches (Chrono24).
    is_sneaker = any(k in pt for k in ['sneaker', 'shoe', 'trainer', 'jordan', 'yeezy'])
    is_luxury_bag = any(k in pt for k in ['bag', 'handbag', 'purse', 'wallet', 'tote'])
    if not is_sneaker and not is_luxury_bag and not is_watch:
        platforms.append({'platform': 'Facebook Marketplace', 'url': f'https://www.facebook.com/marketplace/search/?query={q}'})
        platforms.append({'platform': 'OfferUp',          'url': f'https://offerup.com/search?q={q}'})

    # Electronics-specific platforms
    if is_electronics:
        platforms.append({'platform': 'Swappa', 'url': f'https://swappa.com/search?q={q}'})
        platforms.append({'platform': 'Back Market', 'url': f'https://www.backmarket.com/en-us/search?q={q}'})

    # Watch-specific
    if is_watch:
        platforms.append({'platform': 'Chrono24', 'url': f'https://www.chrono24.com/search/index.htm?query={q}'})

    # Fashion platforms — NOT for electronics or watches
    if not is_electronics and not is_watch:
        platforms.append({'platform': 'Depop', 'url': f'https://www.depop.com/search/?q={q}'})
        platforms.append({'platform': 'Poshmark', 'url': f'https://poshmark.com/search?query={q}'})
        platforms.append({'platform': 'StockX', 'url': f'https://stockx.com/search?s={q}'})

    # Grailed only for clothing/sneakers
    if any(cat in pt for cat in _GRAILED_CATEGORIES):
        platforms.append({'platform': 'Grailed', 'url': f'https://www.grailed.com/shop?query={q}'})

    # Luxury bags — consignment platforms
    if is_luxury_bag:
        platforms.append({'platform': 'Vestiaire Collective', 'url': f'https://www.vestiairecollective.com/search/?q={q}'})
        platforms.append({'platform': 'Fashionphile', 'url': f'https://www.fashionphile.com/shop?search={q}'})
        platforms.append({'platform': 'Rebag', 'url': f'https://www.rebag.com/shop/?q={q}'})

    # Furniture/home decor
    is_furniture = any(k in pt for k in ['furniture', 'chair', 'table', 'lamp', 'decor', 'rug', 'mirror', 'vase', 'cabinet'])
    if is_furniture:
        platforms.append({'platform': 'Chairish', 'url': f'https://www.chairish.com/search?q={q}'})

    # Auction houses — watches, luxury bags, collectibles, furniture/antiques
    is_collectible = any(k in pt for k in ['card', 'toy', 'figure', 'collectible', 'lego', 'funko', 'vinyl', 'art', 'antique', 'coin', 'memorabilia'])
    if is_watch or is_luxury_bag or is_collectible or is_furniture:
        platforms.append({'platform': "Sotheby's", 'url': f'https://www.sothebys.com/en/search?query={q}'})
        platforms.append({'platform': 'Heritage Auctions', 'url': f'https://www.ha.com/search?N=0&Nty=1&Ntt={q}'})
        platforms.append({'platform': "Christie's", 'url': f'https://www.christies.com/en/search?searchPhrase={q}'})

    for p in platforms:
        fee_pct = _PLATFORM_FEES.get(p['platform'], 0.15)
        p['fee_pct'] = round(fee_pct * 100, 1)
        if sell_price > 0:
            p['est_net'] = round(sell_price * (1 - fee_pct), 2)
        else:
            p['est_net'] = 0

    # Sort by highest net profit
    platforms.sort(key=lambda x: x['est_net'], reverse=True)
    return platforms


def _generate_forum_links(query: str, product_type: str) -> list[dict]:
    """Generate category-aware forum, blog, and deal-finding resource links."""
    q = quote_plus(query)
    pt = product_type.lower() if product_type else ''

    is_electronics = any(k in pt for k in ['phone', 'smartphone', 'laptop', 'tablet', 'console', 'electronic',
                                            'camera', 'headphone', 'computer', 'gaming'])
    is_watch = 'watch' in pt
    is_sneaker = any(k in pt for k in ['sneaker', 'shoe', 'trainer', 'jordan', 'yeezy'])
    is_bag = any(k in pt for k in ['bag', 'handbag', 'purse', 'wallet', 'tote'])
    is_collectible = any(k in pt for k in ['card', 'toy', 'figure', 'collectible', 'lego', 'funko', 'vinyl', 'coin'])
    is_clothing = any(k in pt for k in ['clothing', 'jacket', 'shirt', 'hoodie', 'dress', 'coat', 'streetwear'])

    forums = []

    # Universal deal-finding
    forums.append({'name': 'Slickdeals', 'url': f'https://slickdeals.net/newsearch.php?q={q}',
                   'desc': 'Community-sourced deals and price drops'})
    forums.append({'name': 'Reddit Search', 'url': f'https://www.reddit.com/search/?q={q}',
                   'desc': 'Discussions, price checks, and user reviews'})
    forums.append({'name': 'CamelCamelCamel', 'url': f'https://camelcamelcamel.com/search?sq={q}',
                   'desc': 'Amazon price history tracker'})
    forums.append({'name': 'Google Shopping', 'url': f'https://www.google.com/search?tbm=shop&q={q}',
                   'desc': 'Compare prices across all stores'})

    # Sneakers
    if is_sneaker:
        forums.append({'name': 'r/SneakerMarket', 'url': f'https://www.reddit.com/r/sneakermarket/search/?q={q}',
                       'desc': 'Buy/sell/trade sneakers on Reddit'})
        forums.append({'name': 'r/Sneakers', 'url': f'https://www.reddit.com/r/Sneakers/search/?q={q}',
                       'desc': 'Sneaker community discussions and LCs'})
        forums.append({'name': 'Sneaker News', 'url': f'https://sneakernews.com/?s={q}',
                       'desc': 'Release dates, restocks, and market updates'})
        forums.append({'name': 'NikeTalk', 'url': f'https://niketalk.com/search/?q={q}',
                       'desc': 'OG sneaker forum — price discussions and legit checks'})

    # Electronics
    if is_electronics:
        forums.append({'name': 'r/HardwareSwap', 'url': f'https://www.reddit.com/r/hardwareswap/search/?q={q}',
                       'desc': 'Buy/sell electronics on Reddit'})
        forums.append({'name': 'r/Deals', 'url': f'https://www.reddit.com/r/deals/search/?q={q}',
                       'desc': 'Community-posted deals and discounts'})
        forums.append({'name': 'GSMArena', 'url': f'https://www.gsmarena.com/results.php3?sQuickSearch=yes&freeText={q}',
                       'desc': 'Phone specs, reviews, and price comparison'})

    # Watches
    if is_watch:
        forums.append({'name': 'WatchUSeek', 'url': f'https://www.watchuseek.com/search/?q={q}',
                       'desc': 'Largest watch forum — market values and discussions'})
        forums.append({'name': 'r/WatchExchange', 'url': f'https://www.reddit.com/r/Watchexchange/search/?q={q}',
                       'desc': 'Buy/sell watches on Reddit'})
        forums.append({'name': 'Hodinkee', 'url': f'https://www.hodinkee.com/search?q={q}',
                       'desc': 'Watch reviews, market analysis, and valuations'})

    # Bags / luxury fashion
    if is_bag:
        forums.append({'name': 'PurseForum', 'url': f'https://forum.purseblog.com/search/?q={q}',
                       'desc': 'Largest handbag community — auth tips and market prices'})
        forums.append({'name': 'r/Handbags', 'url': f'https://www.reddit.com/r/handbags/search/?q={q}',
                       'desc': 'Handbag discussions, price checks, and reviews'})

    # Collectibles
    if is_collectible:
        forums.append({'name': 'r/FlippingCollectibles', 'url': f'https://www.reddit.com/r/Flipping/search/?q={q}',
                       'desc': 'Resale community — flipping strategies and finds'})

    # Clothing / streetwear
    if is_clothing or is_sneaker:
        forums.append({'name': 'r/FashionRepsBST', 'url': f'https://www.reddit.com/r/FashionRepsBST/search/?q={q}',
                       'desc': 'Fashion buy/sell/trade community'})
        forums.append({'name': 'Hypebeast', 'url': f'https://hypebeast.com/?s={q}',
                       'desc': 'Streetwear news, drops, and resale market updates'})

    return forums


def _validate_links(urls: list[str]) -> dict[str, bool]:
    """Validate URLs with parallel HEAD requests. Returns {url: verified}."""
    results = {}
    if not urls:
        return results

    def _check(url):
        try:
            resp = requests.head(url, timeout=5, allow_redirects=True,
                                 headers={'User-Agent': 'Mozilla/5.0'})
            return url, resp.status_code < 400
        except Exception:
            return url, False

    with ThreadPoolExecutor(max_workers=8) as executor:
        for url, ok in executor.map(_check, urls):
            results[url] = ok
    return results


def allowed_file(filename):
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'jpg', 'jpeg', 'png', 'webp'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def _run_analysis_bg(app, analysis_id, user_id, image_base64, image_media_type,
                     text_input, link_input, has_text, has_link):
    with app.app_context():
        analysis = Analysis.query.get(analysis_id)
        if not analysis:
            return
        try:
            # Agent 1: Extract product details
            extracted = extract_product_details(
                text_input=text_input if has_text else None,
                image_base64=image_base64,
                image_media_type=image_media_type,
                link=link_input if has_link else None
            )
            analysis.extracted_product = json.dumps(extracted)
            db.session.commit()

            search_query = extracted.get('search_query', text_input or 'product')
            # For image and link inputs, the AI's search_query can be wrong (URL fragments,
            # over-specified, or referencing a misidentified product). Always build a clean
            # query from extracted fields: brand + product_type + model.
            if image_base64 or has_link:
                parts = [
                    extracted.get('brand', ''),
                    extracted.get('product_type', ''),
                    extracted.get('model', ''),
                ]
                simple_query = ' '.join(p for p in parts if p and p.lower() not in ('unknown', '')).strip()
                if simple_query:
                    search_query = simple_query

            # Currency conversion: if listing price is in a foreign currency, convert to USD
            listing_currency = (extracted.get('listing_currency') or 'USD').upper()
            raw_listing_price = float(extracted.get('listing_price', 0) or 0)
            if listing_currency != 'USD' and raw_listing_price > 0:
                converted_price, conv_method = convert_to_usd(raw_listing_price, listing_currency)
                extracted['listing_price_original'] = raw_listing_price
                extracted['listing_price_original_currency'] = listing_currency
                extracted['listing_price'] = converted_price
                extracted['currency_conversion_method'] = conv_method
                # Re-save extracted with converted price
                analysis.extracted_product = json.dumps(extracted)
                db.session.commit()

            # When a URL was submitted, the listing price on that page IS the buy price.
            # Pass it through so the sourcing agent anchors cheapest_found to the real price.
            input_price = float(extracted.get('listing_price', 0) or 0) if has_link else 0

            # Small delay between agents to avoid Gemini 15 RPM rate limit
            import time as _time
            _time.sleep(2)

            # Agent 2: Pricing first (sourcing needs avg_sold to compute target buy price)
            pricing = research_prices(search_query, extracted)
            analysis.price_research = json.dumps(pricing)
            db.session.commit()

            _time.sleep(2)

            # Agent 3: Sourcing with real avg_sold data
            avg_sold = pricing.get('avg_sold', 0) or 0
            sourcing = find_sourcing_deals(search_query, avg_sold, extracted, input_price)

            # Cross-validation: detect buy/sell spread anomalies
            cheapest = sourcing.get('cheapest_found', 0) or 0
            if avg_sold > 0 and cheapest > 0:
                spread_pct = (avg_sold - cheapest) / avg_sold
                if cheapest > avg_sold:
                    sourcing['market_spread_warning'] = (
                        f"WARNING: Cheapest available (${cheapest:.0f}) exceeds median sold (${avg_sold:.0f}). "
                        f"The market may be cooling or listings are overpriced. Wait for a price drop."
                    )
                elif spread_pct < 0.10:
                    sourcing['market_spread_warning'] = (
                        f"Tight market: cheapest listing (${cheapest:.0f}) is within {round(spread_pct*100)}% "
                        f"of median sold price (${avg_sold:.0f}). Profit margin will be very thin after fees."
                    )

            # Buy links: Google Shopping (primary) + eBay Browse API (supplement)
            buy_links = []
            seen_urls = set()

            # If the user submitted a URL, include the original listing first
            if has_link and link_input:
                original_link = {
                    'title': extracted.get('brand', '') + ' ' + extracted.get('model', '') + ' (Original Listing)',
                    'price': input_price,
                    'shipping_cost': 0,
                    'total_price': input_price,
                    'condition': extracted.get('condition_grade', ''),
                    'url': link_input,
                    'image_url': '',
                    'platform': 'Original Listing',
                    'verified': True,
                }
                buy_links.append(original_link)
                seen_urls.add(link_input)

            # Google Shopping: real price comparison across Amazon, eBay, Walmart, etc.
            try:
                shopping_results = _search_google_shopping(search_query, limit=8)
                for item in shopping_results:
                    if item['url'] not in seen_urls:
                        buy_links.append(item)
                        seen_urls.add(item['url'])
            except Exception as e:
                logger.warning(f"Google Shopping search failed: {e}")

            # eBay Browse API: supplement with direct eBay listings
            try:
                ebay_listings = search_ebay(search_query, limit=5)
                for item in ebay_listings:
                    if item.get('url') and item['url'] not in seen_urls:
                        buy_links.append(item)
                        seen_urls.add(item['url'])
            except Exception as e:
                logger.warning(f"eBay buy-links search failed: {e}")

            # Keep top 8 results (original listing + best prices)
            buy_links = buy_links[:8]

            # Build sell_links (platform search URLs with fee estimates) — always succeeds
            sell_links = []
            try:
                sell_price = pricing.get('recommended_sell_price', 0) or 0
                product_type = (extracted.get('product_type') or '').lower()
                sell_links = _generate_sell_links(search_query, product_type, sell_price)
            except Exception as e:
                logger.warning(f"Sell links generation failed: {e}")

            # Validate all URLs in parallel (non-blocking — failures are silent)
            try:
                all_urls = [l['url'] for l in buy_links if l.get('url')]
                all_urls += [l['url'] for l in sell_links if l.get('url')]
                if all_urls:
                    verified_urls = _validate_links(all_urls)
                    for link_item in buy_links:
                        link_item['verified'] = verified_urls.get(link_item.get('url', ''), False)
                    for link_item in sell_links:
                        link_item['verified'] = verified_urls.get(link_item.get('url', ''), False)
            except Exception as e:
                logger.warning(f"Link validation failed: {e}")

            sourcing['buy_links'] = buy_links
            sourcing['sell_links'] = sell_links

            # Update cheapest_found with real buy link data so arbitrage uses accurate price
            if buy_links:
                verified_prices = [l['total_price'] for l in buy_links
                                   if l.get('total_price', 0) > 0 and l.get('verified')]
                all_real_prices = [l['total_price'] for l in buy_links
                                   if l.get('total_price', 0) > 0]
                real_prices = verified_prices or all_real_prices
                logger.info(f"Analysis {analysis_id}: buy_links={len(buy_links)}, "
                            f"verified_prices={verified_prices}, all_real_prices={all_real_prices}")
                if real_prices:
                    cheapest_real = min(real_prices)
                    ai_cheapest = sourcing.get('cheapest_found', 0) or 0
                    # Use real price if it's valid and lower than AI estimate (or AI had nothing)
                    if cheapest_real > 0 and (ai_cheapest <= 0 or cheapest_real < ai_cheapest):
                        sourcing['cheapest_found'] = cheapest_real
                        sourcing['cheapest_found_source'] = 'verified_listing'
                        logger.info(f"Analysis {analysis_id}: Updated cheapest_found from AI ${ai_cheapest:.0f} to real ${cheapest_real:.2f}")
                    else:
                        logger.info(f"Analysis {analysis_id}: Kept AI cheapest_found=${ai_cheapest:.0f} "
                                    f"(real cheapest=${cheapest_real:.2f})")

            # Forum & blog links for deal-finding and community research
            forum_links = []
            try:
                product_type = (extracted.get('product_type') or '').lower()
                forum_links = _generate_forum_links(search_query, product_type)
            except Exception as e:
                logger.warning(f"Forum links generation failed: {e}")
            sourcing['forum_links'] = forum_links

            analysis.sourcing_results = json.dumps(sourcing)
            db.session.commit()
            logger.info(f"Analysis {analysis_id}: {len(buy_links)} buy, {len(sell_links)} sell, {len(forum_links)} forum links saved")

            _time.sleep(2)

            # Agent 4: Arbitrage
            arbitrage = calculate_arbitrage(pricing, sourcing, product_info=extracted)
            # Tag whether ROI is based on a real listing price or an AI estimate
            has_real_price = (input_price > 0) or sourcing.get('cheapest_found_source') == 'verified_listing'
            arbitrage['roi_data_source'] = 'real' if has_real_price else 'estimated'
            analysis.arbitrage_result = json.dumps(arbitrage)

            # Trends + Social in parallel (non-blocking — failures are silent)
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_trend = executor.submit(get_trend_data, search_query)
                future_social = executor.submit(get_social_data, search_query)
                trend = future_trend.result()
                social = future_social.result()

            if trend:
                analysis.trend_data = json.dumps(trend)
            if social:
                analysis.social_data = json.dumps(social)

            analysis.status = 'complete'

            from models.user import User
            user = User.query.get(user_id)
            if user:
                user.analyses_used_this_month += 1
            db.session.commit()

            # Trim history to 10 per user
            all_user_analyses = Analysis.query.filter_by(user_id=user_id).order_by(
                Analysis.created_at.desc()
            ).all()
            if len(all_user_analyses) > 10:
                for old in all_user_analyses[10:]:
                    db.session.delete(old)
                db.session.commit()

        except Exception as e:
            try:
                analysis = Analysis.query.get(analysis_id)
                if analysis:
                    analysis.status = 'error'
                    analysis.error_message = str(e)[:1000]
                    db.session.commit()
            except Exception:
                pass


@analysis_bp.route('/submit', methods=['POST'])
@login_required
@limiter.limit("10 per hour")
def submit():
    # Reset monthly counter if we've rolled into a new month
    current_user.reset_monthly_if_needed()
    if not current_user.can_analyse():
        if current_user.subscription_tier == 'free':
            flash("You've used all 3 free analyses this month. Upgrade to Pro for 50/month — includes a 10-day free trial.", 'warning')
        elif current_user.subscription_tier == 'premium':
            flash("You've reached your 300 analyses this month. Need more? Email us at hello@zzi.ai about our Enterprise plan.", 'warning')
        else:
            flash('Monthly analysis limit reached. Your limit resets at the start of next month.', 'warning')
        return redirect(url_for('billing.pricing'))

    image_file = request.files.get('image')
    text_input = request.form.get('description', '').strip()
    link_input = request.form.get('link', '').strip()

    max_len = current_app.config.get('MAX_TEXT_INPUT_LENGTH', 2000)
    if text_input:
        text_input = text_input[:max_len]

    has_image = image_file and image_file.filename

    # 24-hour cooldown: block re-analysis of the same text/link within 24 hours
    # Admins bypass cooldown for testing
    raw_for_check = (link_input or text_input)[:4000] if (link_input or text_input) else None
    if raw_for_check and not has_image and not current_user.is_admin:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_dupe = Analysis.query.filter(
            Analysis.user_id == current_user.id,
            Analysis.raw_input == raw_for_check,
            Analysis.status == 'complete',
            Analysis.created_at >= cutoff
        ).first()
        if recent_dupe:
            flash("This item was already analysed in the last 24 hours — market prices don't update that fast. "
                  "Check back tomorrow for fresh data.", 'warning')
            return redirect(url_for('analysis.results', id=recent_dupe.id))

    # Image analysis is Premium-only
    if has_image and current_user.subscription_tier not in ('premium',) and not current_user.is_admin:
        flash('Image analysis is a Premium feature. Upgrade to unlock photo-based flip analysis.', 'warning')
        return redirect(url_for('billing.pricing'))
    has_text = bool(text_input)
    has_link = bool(link_input)

    if not (has_image or has_text or has_link):
        flash('Please provide an image, description, or product URL.', 'danger')
        return redirect(url_for('analysis.input_page'))

    image_base64 = None
    image_media_type = None

    if has_image:
        if not allowed_file(image_file.filename):
            flash('Invalid file type. Please upload JPG, PNG, or WebP.', 'danger')
            return redirect(url_for('analysis.input_page'))
        ext = image_file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        upload_folder = current_app.config['UPLOAD_FOLDER']
        image_path = os.path.join(upload_folder, filename)
        image_file.save(image_path)
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        # Validate that the file is actually an image (MIME check via Pillow)
        try:
            img = PilImage.open(io.BytesIO(image_bytes))
            img.verify()
        except Exception:
            os.remove(image_path)
            flash('Invalid image file. Please upload a real JPG, PNG, or WebP.', 'danger')
            return redirect(url_for('analysis.input_page'))
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        media_map = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}
        image_media_type = media_map.get(ext, 'image/jpeg')
        os.remove(image_path)

    input_type = 'image' if has_image else ('link' if has_link else 'text')
    raw_input = (link_input or text_input or image_file.filename or '')[:4000]

    analysis = Analysis(
        user_id=current_user.id,
        input_type=input_type,
        raw_input=raw_input,
        status='processing'
    )
    db.session.add(analysis)
    db.session.commit()

    app_obj = current_app._get_current_object()
    t = Thread(
        target=_run_analysis_bg,
        args=(app_obj, analysis.id, current_user.id, image_base64, image_media_type,
              text_input, link_input, has_text, has_link),
        daemon=True
    )
    t.start()

    return redirect(url_for('analysis.progress', id=analysis.id))


@analysis_bp.route('/')
@login_required
def input_page():
    return render_template('analysis/input.html')


@analysis_bp.route('/progress/<int:id>')
@login_required
def progress(id):
    analysis = Analysis.query.get_or_404(id)
    if analysis.user_id != current_user.id and not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard.home'))
    return render_template('analysis/progress.html', analysis=analysis)


@analysis_bp.route('/status/<int:id>')
@login_required
def status(id):
    analysis = Analysis.query.get_or_404(id)
    if analysis.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    return jsonify({
        'status': analysis.status,
        'error_message': analysis.error_message,
        'extracted_product': analysis.get_extracted() if analysis.extracted_product else None,
        'price_research': analysis.get_pricing() if analysis.price_research else None,
        'sourcing_results': analysis.get_sourcing() if analysis.sourcing_results else None,
        'arbitrage_result': analysis.get_arbitrage() if analysis.arbitrage_result else None,
        'raw_input': analysis.raw_input,
    })


@analysis_bp.route('/results/<int:id>')
@login_required
def results(id):
    analysis = Analysis.query.get_or_404(id)
    if analysis.user_id != current_user.id and not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard.home'))
    return render_template('analysis/results.html', analysis=analysis)


@analysis_bp.route('/export/<int:id>')
@login_required
def export(id):
    """Clean print/PDF export page for Premium users."""
    analysis = Analysis.query.get_or_404(id)
    if analysis.user_id != current_user.id and not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard.home'))
    if current_user.subscription_tier not in ('premium',) and not current_user.is_admin:
        flash('PDF export is a Premium feature. Upgrade to download reports.', 'warning')
        return redirect(url_for('analysis.results', id=id))
    arb      = analysis.get_arbitrage()
    pricing  = analysis.get_pricing()
    sourcing = analysis.get_sourcing()
    extracted = analysis.get_extracted()
    roi      = analysis.get_roi_value()
    url_is_source = sourcing.get('url_is_source', False) if sourcing else False
    return render_template('analysis/export.html',
        analysis=analysis, arb=arb, pricing=pricing,
        sourcing=sourcing, extracted=extracted, roi=roi,
        url_is_source=url_is_source)


@analysis_bp.route('/public/<int:id>')
def public_results(id):
    """View a shared analysis without login."""
    analysis = Analysis.query.get_or_404(id)
    if not analysis.is_public:
        flash('This analysis is not publicly shared.', 'warning')
        return redirect(url_for('auth.landing'))
    return render_template('analysis/results.html', analysis=analysis, public_view=True)


@analysis_bp.route('/<int:id>/toggle_public', methods=['POST'])
@login_required
def toggle_public(id):
    analysis = Analysis.query.get_or_404(id)
    if analysis.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    analysis.is_public = not analysis.is_public
    db.session.commit()
    public_url = url_for('analysis.public_results', id=id, _external=True) if analysis.is_public else None
    return jsonify({'is_public': analysis.is_public, 'public_url': public_url})


@analysis_bp.route('/trending')
@login_required
def trending():
    """Return recent analyses (anonymized) for the 'What others are flipping' widget."""
    try:
        since = datetime.utcnow() - timedelta(days=7)
        recent = Analysis.query.filter(
            Analysis.status == 'complete',
            Analysis.created_at >= since,
            Analysis.extracted_product.isnot(None),
        ).order_by(Analysis.created_at.desc()).limit(30).all()

        items = []
        seen = set()
        for a in recent:
            ext = a.get_extracted()
            if not ext:
                continue
            name = ' '.join(
                p for p in [ext.get('brand', ''), ext.get('product_type', ''), ext.get('model', '')]
                if p and p.lower() not in ('unknown', '')
            ).strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())

            arb = a.get_arbitrage()
            roi = arb.get('roi_percent', 0) if arb else 0
            verdict = arb.get('verdict', '') if arb else ''
            category = a.get_category() if hasattr(a, 'get_category') else 'Other'

            items.append({
                'name': name[:60],
                'category': category,
                'roi': round(float(roi or 0)),
                'verdict': verdict,
            })
            if len(items) >= 10:
                break

        return jsonify({'items': items})
    except Exception as e:
        logger.warning(f"Trending endpoint error: {e}")
        return jsonify({'items': []})
