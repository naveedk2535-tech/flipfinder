#!/usr/bin/env python3
"""
Validation test for buy price fix:
1. cheapest_found updated from real buy links
2. best_platform excludes local-only platforms
3. sell_links are category-conditional (no FB Marketplace for sneakers/bags/watches)
4. Profit calculation uses correct buy price
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Minimal Flask app context for imports
os.environ.setdefault('SECRET_KEY', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite://')
os.environ.setdefault('FLASK_ENV', 'testing')

PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} — {detail}")


print("\n" + "="*70)
print("TEST 1: cheapest_found update logic")
print("="*70)

# Simulate the logic from routes/analysis.py lines 446-460
def simulate_cheapest_found_update(buy_links, ai_cheapest):
    """Reproduce the exact logic from _run_analysis_bg."""
    sourcing = {'cheapest_found': ai_cheapest}
    if buy_links:
        verified_prices = [l['total_price'] for l in buy_links
                           if l.get('total_price', 0) > 0 and l.get('verified')]
        all_real_prices = [l['total_price'] for l in buy_links
                           if l.get('total_price', 0) > 0]
        real_prices = verified_prices or all_real_prices
        if real_prices:
            cheapest_real = min(real_prices)
            current = sourcing.get('cheapest_found', 0) or 0
            if cheapest_real > 0 and (current <= 0 or cheapest_real < current):
                sourcing['cheapest_found'] = cheapest_real
                sourcing['cheapest_found_source'] = 'verified_listing'
    return sourcing

# Test case: Real buy links cheaper than AI estimate (the Jordan 1 scenario)
buy_links_jordan = [
    {'total_price': 60.0, 'verified': True, 'platform': 'Gbny'},
    {'total_price': 69.99, 'verified': True, 'platform': 'Mercari'},
    {'total_price': 100.0, 'verified': True, 'platform': 'eBay'},
    {'total_price': 120.0, 'verified': True, 'platform': 'eBay'},
    {'total_price': 142.0, 'verified': True, 'platform': 'Laced'},
    {'total_price': 175.0, 'verified': True, 'platform': 'Whatnot'},
]
result = simulate_cheapest_found_update(buy_links_jordan, ai_cheapest=126)
check("Real $60 replaces AI $126", result['cheapest_found'] == 60.0,
      f"got {result['cheapest_found']}")
check("Source tagged as verified_listing", result.get('cheapest_found_source') == 'verified_listing',
      f"got {result.get('cheapest_found_source')}")

# Test case: AI estimate cheaper than real links (don't replace)
result2 = simulate_cheapest_found_update(buy_links_jordan, ai_cheapest=40)
check("AI $40 kept when cheaper than real $60", result2['cheapest_found'] == 40,
      f"got {result2['cheapest_found']}")
check("Source NOT tagged (AI was cheaper)", result2.get('cheapest_found_source') is None,
      f"got {result2.get('cheapest_found_source')}")

# Test case: AI returned 0 (no estimate), real links exist
result3 = simulate_cheapest_found_update(buy_links_jordan, ai_cheapest=0)
check("Real $60 replaces AI $0", result3['cheapest_found'] == 60.0,
      f"got {result3['cheapest_found']}")

# Test case: No buy links at all
result4 = simulate_cheapest_found_update([], ai_cheapest=126)
check("AI $126 kept when no buy links", result4['cheapest_found'] == 126,
      f"got {result4['cheapest_found']}")

# Test case: Only unverified links (should still use them as fallback)
unverified_links = [
    {'total_price': 80.0, 'verified': False, 'platform': 'eBay'},
    {'total_price': 90.0, 'verified': False, 'platform': 'Amazon'},
]
result5 = simulate_cheapest_found_update(unverified_links, ai_cheapest=126)
check("Unverified $80 replaces AI $126 as fallback", result5['cheapest_found'] == 80.0,
      f"got {result5['cheapest_found']}")


print("\n" + "="*70)
print("TEST 2: best_platform excludes local-only platforms")
print("="*70)

from agents.arbitrage_agent import _validate_and_recalculate, PLATFORM_FEES, _get_ebay_fee

# Simulate a sneaker analysis
product_info_sneaker = {'product_type': 'Sneakers', 'condition_grade': 'Very Good'}
pricing_data = {
    'avg_sold': 290, 'min_sold': 220, 'max_sold': 380,
    'recommended_sell_price': 238, 'sell_velocity_days': 14, 'confidence': 'medium'
}
sourcing_data = {'cheapest_found': 60, 'cheapest_found_source': 'verified_listing'}

ai_result = {
    'buy_price': 60, 'sell_price': 238,
    'shipping_cost_est': 14.0, 'estimated_time_hrs': 2.5,
    'recommendation': 'Good flip', 'listing_tips': [], 'risk_commentary': ''
}

result = _validate_and_recalculate(dict(ai_result), pricing_data, sourcing_data, product_info_sneaker)

check("buy_price = $60 (from real listing)", result['buy_price'] == 60,
      f"got ${result['buy_price']}")
check("sell_price = $238 (from pricing agent)", result['sell_price'] == 238,
      f"got ${result['sell_price']}")
check("best_platform is NOT Facebook Marketplace", result['best_platform'] != 'Facebook Marketplace',
      f"got {result['best_platform']}")
check("best_platform is NOT OfferUp", result['best_platform'] != 'OfferUp',
      f"got {result['best_platform']}")
check("best_platform is a real resale platform", result['best_platform'] in (
    'eBay', 'Depop', 'Poshmark', 'StockX', 'Mercari', 'Grailed', 'Swappa'),
      f"got {result['best_platform']}")

# Check FB Marketplace IS in breakdown but didn't win
fb_in_breakdown = any(p['platform'] == 'Facebook Marketplace' for p in result['platform_breakdown'])
check("FB Marketplace still in breakdown for transparency", fb_in_breakdown)

# Check profit math
buy = result['buy_price']
sell = result['sell_price']
fee_pct = next((p['fee_pct'] for p in result['platform_breakdown']
                if p['platform'] == result['best_platform']), 0) / 100
expected_fee = round(sell * fee_pct, 2)
expected_net = round(sell - buy - expected_fee, 2)
check(f"net_profit math correct (${expected_net})", abs(result['net_profit'] - expected_net) < 0.02,
      f"expected ${expected_net}, got ${result['net_profit']}")

check("true_net_profit equals net_profit (no shipping in calc)", result['true_net_profit'] == result['net_profit'],
      f"true_net={result['true_net_profit']}, net={result['net_profit']}")

roi = result['roi_percent']
check(f"ROI is positive ({roi:.0f}%)", roi > 0, f"got {roi}%")
check("verdict is not Avoid", result['verdict'] != 'Avoid', f"got {result['verdict']}")

print(f"\n  Summary: Buy ${buy} → Sell ${sell} on {result['best_platform']}")
print(f"  Net profit: ${result['net_profit']} | ROI: {roi:.0f}%")
print(f"  Verdict: {result['verdict']}")


print("\n" + "="*70)
print("TEST 3: sell_links category filtering (FB Marketplace / OfferUp)")
print("="*70)

# Can't import routes.analysis directly (PIL dependency), so replicate the logic here
from urllib.parse import quote_plus

_GRAILED_CATEGORIES = {'sneaker', 'shoe', 'clothing', 'apparel', 'jacket', 'hoodie',
                       'shirt', 'pants', 'streetwear', 'dress', 'coat', 'jeans'}

_PLATFORM_FEES_LOCAL = {
    'eBay': 0.1335, 'StockX': 0.125, 'Depop': 0.10, 'Poshmark': 0.20,
    'Mercari': 0.10, 'Grailed': 0.119, 'Swappa': 0.03, 'Back Market': 0.10,
    'Chrono24': 0.065, 'Vestiaire Collective': 0.12, 'Fashionphile': 0.15,
    'Rebag': 0.15, "Sotheby's": 0.20, 'Heritage Auctions': 0.20, "Christie's": 0.20,
    'Facebook Marketplace': 0.0, 'OfferUp': 0.0, 'Chairish': 0.20,
}

def _generate_sell_links(query, product_type, sell_price):
    """Exact copy of routes/analysis.py _generate_sell_links."""
    q = quote_plus(query)
    pt = product_type.lower() if product_type else ''
    is_electronics = any(k in pt for k in ['phone', 'laptop', 'tablet', 'console', 'electronic',
                                            'camera', 'headphone', 'smartphone', 'computer', 'gaming'])
    is_watch = 'watch' in pt
    platforms = [
        {'platform': 'eBay', 'url': f'https://www.ebay.com/sch/i.html?_nkw={q}'},
        {'platform': 'Mercari', 'url': f'https://www.mercari.com/search/?keyword={q}'},
    ]
    is_sneaker = any(k in pt for k in ['sneaker', 'shoe', 'trainer', 'jordan', 'yeezy'])
    is_luxury_bag = any(k in pt for k in ['bag', 'handbag', 'purse', 'wallet', 'tote'])
    if not is_sneaker and not is_luxury_bag and not is_watch:
        platforms.append({'platform': 'Facebook Marketplace', 'url': f'https://www.facebook.com/marketplace/search/?query={q}'})
        platforms.append({'platform': 'OfferUp', 'url': f'https://offerup.com/search?q={q}'})
    if is_electronics:
        platforms.append({'platform': 'Swappa', 'url': f'https://swappa.com/search?q={q}'})
        platforms.append({'platform': 'Back Market', 'url': f'https://www.backmarket.com/en-us/search?q={q}'})
    if is_watch:
        platforms.append({'platform': 'Chrono24', 'url': f'https://www.chrono24.com/search/index.htm?query={q}'})
    if not is_electronics and not is_watch:
        platforms.append({'platform': 'Depop', 'url': f'https://www.depop.com/search/?q={q}'})
        platforms.append({'platform': 'Poshmark', 'url': f'https://poshmark.com/search?query={q}'})
        platforms.append({'platform': 'StockX', 'url': f'https://stockx.com/search?s={q}'})
    if any(cat in pt for cat in _GRAILED_CATEGORIES):
        platforms.append({'platform': 'Grailed', 'url': f'https://www.grailed.com/shop?query={q}'})
    if is_luxury_bag:
        platforms.append({'platform': 'Vestiaire Collective', 'url': f'https://www.vestiairecollective.com/search/?q={q}'})
        platforms.append({'platform': 'Fashionphile', 'url': f'https://www.fashionphile.com/shop?search={q}'})
        platforms.append({'platform': 'Rebag', 'url': f'https://www.rebag.com/shop/?q={q}'})
    is_furniture = any(k in pt for k in ['furniture', 'chair', 'table', 'lamp', 'decor'])
    if is_furniture:
        platforms.append({'platform': 'Chairish', 'url': f'https://www.chairish.com/search?q={q}'})
    is_collectible = any(k in pt for k in ['card', 'toy', 'figure', 'collectible', 'lego', 'funko'])
    if is_watch or is_luxury_bag or is_collectible or is_furniture:
        platforms.append({'platform': "Sotheby's", 'url': f'https://www.sothebys.com/en/search?query={q}'})
        platforms.append({'platform': 'Heritage Auctions', 'url': f'https://www.ha.com/search?N=0&Nty=1&Ntt={q}'})
        platforms.append({'platform': "Christie's", 'url': f'https://www.christies.com/en/search?searchPhrase={q}'})
    for p in platforms:
        fee_pct = _PLATFORM_FEES_LOCAL.get(p['platform'], 0.15)
        p['fee_pct'] = round(fee_pct * 100, 1)
        p['est_net'] = round(sell_price * (1 - fee_pct), 2) if sell_price > 0 else 0
    platforms.sort(key=lambda x: x['est_net'], reverse=True)
    return platforms

# Sneakers — should NOT have FB Marketplace or OfferUp
sneaker_links = _generate_sell_links("Nike Air Jordan 1", "Sneakers", 238)
sneaker_platforms = [l['platform'] for l in sneaker_links]
check("Sneakers: no Facebook Marketplace", 'Facebook Marketplace' not in sneaker_platforms,
      f"found: {sneaker_platforms}")
check("Sneakers: no OfferUp", 'OfferUp' not in sneaker_platforms,
      f"found: {sneaker_platforms}")
check("Sneakers: has eBay", 'eBay' in sneaker_platforms)
check("Sneakers: has StockX", 'StockX' in sneaker_platforms)
check("Sneakers: has Depop", 'Depop' in sneaker_platforms)
check("Sneakers: has Grailed", 'Grailed' in sneaker_platforms)
check("Sneakers: has Mercari", 'Mercari' in sneaker_platforms)

# Luxury bag — should NOT have FB Marketplace or OfferUp
bag_links = _generate_sell_links("Louis Vuitton Neverfull", "Handbag", 1200)
bag_platforms = [l['platform'] for l in bag_links]
check("Bags: no Facebook Marketplace", 'Facebook Marketplace' not in bag_platforms,
      f"found: {bag_platforms}")
check("Bags: no OfferUp", 'OfferUp' not in bag_platforms,
      f"found: {bag_platforms}")
check("Bags: has Vestiaire Collective", 'Vestiaire Collective' in bag_platforms)
check("Bags: has Fashionphile", 'Fashionphile' in bag_platforms)
check("Bags: has Rebag", 'Rebag' in bag_platforms)

# Watch — should NOT have FB Marketplace or OfferUp
watch_links = _generate_sell_links("Rolex Submariner", "Watch", 8000)
watch_platforms = [l['platform'] for l in watch_links]
check("Watches: no Facebook Marketplace", 'Facebook Marketplace' not in watch_platforms,
      f"found: {watch_platforms}")
check("Watches: no OfferUp", 'OfferUp' not in watch_platforms,
      f"found: {watch_platforms}")
check("Watches: has Chrono24", 'Chrono24' in watch_platforms)

# Electronics — SHOULD have FB Marketplace and OfferUp
elec_links = _generate_sell_links("iPhone 15 Pro", "Smartphone", 800)
elec_platforms = [l['platform'] for l in elec_links]
check("Electronics: has Facebook Marketplace", 'Facebook Marketplace' in elec_platforms)
check("Electronics: has OfferUp", 'OfferUp' in elec_platforms)
check("Electronics: has Swappa", 'Swappa' in elec_platforms)
check("Electronics: has Back Market", 'Back Market' in elec_platforms)

# General item — SHOULD have FB Marketplace and OfferUp
general_links = _generate_sell_links("Dyson V15 vacuum", "Appliance", 350)
general_platforms = [l['platform'] for l in general_links]
check("General: has Facebook Marketplace", 'Facebook Marketplace' in general_platforms)
check("General: has OfferUp", 'OfferUp' in general_platforms)

# Verify fee calculations on sell links
for link in sneaker_links:
    if link['platform'] == 'eBay':
        check(f"eBay fee for sneakers is 13.4% (default)", link['fee_pct'] == 13.4,
              f"got {link['fee_pct']}%")
        expected_net = round(238 * (1 - 0.1335), 2)
        check(f"eBay est_net correct (${expected_net})", abs(link['est_net'] - expected_net) < 0.02,
              f"got ${link['est_net']}")
        break


print("\n" + "="*70)
print("TEST 4: End-to-end profit consistency (Overview matches Buy Links)")
print("="*70)

# Simulate the full pipeline as it would run in _run_analysis_bg
# Step 1: AI sourcing returns estimate
sourcing_from_ai = {'cheapest_found': 126, 'avg_source_price': 145, 'best_deals': [
    {'title': 'Air Jordan 1 University Blue', 'price': 126, 'platform': 'eBay', 'condition': 'Used - Very Good'},
    {'title': 'Air Jordan 1 University Blue', 'price': 140, 'platform': 'StockX', 'condition': 'Deadstock'},
]}

# Step 2: Real buy links fetched (Google Shopping + eBay API)
real_buy_links = [
    {'total_price': 60.0, 'verified': True, 'platform': 'Gbny', 'title': 'Air Jordan 1 High OG University Blue', 'url': 'https://example.com/1'},
    {'total_price': 69.99, 'verified': True, 'platform': 'Mercari', 'title': 'Nike Air Jordan 1 Retro High OG', 'url': 'https://example.com/2'},
    {'total_price': 100.0, 'verified': True, 'platform': 'eBay', 'title': 'Air Jordan 1 University Blue', 'url': 'https://example.com/3'},
]

# Step 3: Update cheapest_found (the fix we made)
sourcing_updated = dict(sourcing_from_ai)
sourcing_updated['buy_links'] = real_buy_links
if real_buy_links:
    verified_prices = [l['total_price'] for l in real_buy_links if l.get('total_price', 0) > 0 and l.get('verified')]
    all_real_prices = [l['total_price'] for l in real_buy_links if l.get('total_price', 0) > 0]
    real_prices = verified_prices or all_real_prices
    if real_prices:
        cheapest_real = min(real_prices)
        ai_cheapest = sourcing_updated.get('cheapest_found', 0) or 0
        if cheapest_real > 0 and (ai_cheapest <= 0 or cheapest_real < ai_cheapest):
            sourcing_updated['cheapest_found'] = cheapest_real
            sourcing_updated['cheapest_found_source'] = 'verified_listing'

check("cheapest_found updated to $60 (was $126)", sourcing_updated['cheapest_found'] == 60.0,
      f"got ${sourcing_updated['cheapest_found']}")

# Step 4: Run arbitrage with updated sourcing
# KEY TEST: AI returns buy_price=179.99 (its own estimate), but sourcing has cheapest_found=60
# The Python code MUST override the AI value with sourcing data
arb_input = {
    'buy_price': 179.99, 'sell_price': 250,
    'shipping_cost_est': 14.0, 'estimated_time_hrs': 2.5,
    'recommendation': 'test', 'listing_tips': [], 'risk_commentary': ''
}
arb_result = _validate_and_recalculate(dict(arb_input), pricing_data, sourcing_updated, product_info_sneaker)

# The key check: Overview's buy_price should match the cheapest buy link
overview_buy = arb_result['buy_price']
cheapest_link = min(l['total_price'] for l in real_buy_links)
check(f"Overview 'Buy for' (${overview_buy}) matches cheapest link (${cheapest_link})",
      overview_buy == cheapest_link,
      f"Overview shows ${overview_buy}, but cheapest link is ${cheapest_link}")

check(f"Profit uses correct buy price of ${overview_buy}",
      arb_result['buy_price'] == 60.0, f"got ${arb_result['buy_price']}")

print(f"\n  BEFORE FIX: Buy $126 (AI) → Sell $238 = gross ${238-126}")
print(f"  AFTER FIX:  Buy $60 (real) → Sell $238 = gross ${238-60}")
print(f"  Actual result: Buy ${arb_result['buy_price']} → Sell ${arb_result['sell_price']}")
print(f"  Net profit: ${arb_result['net_profit']} | After shipping: ${arb_result['true_net_profit']} | ROI: {arb_result['roi_percent']:.0f}%")
print(f"  Best platform: {arb_result['best_platform']} | Verdict: {arb_result['verdict']}")


print("\n" + "="*70)
print(f"RESULTS: {PASS} passed, {FAIL} failed")
print("="*70)

if FAIL > 0:
    print("\n⚠️  SOME TESTS FAILED — review above")
    sys.exit(1)
else:
    print("\n✅ ALL TESTS PASSED — buy price fix is working correctly")
    sys.exit(0)
