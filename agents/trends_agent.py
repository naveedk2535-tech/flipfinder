"""
Google Trends + Social data fetcher.
Trends:   Google Trends embed widget (client-side, no API key needed)
Reddit:   Reddit OAuth API (official) → Reddit public JSON
YouTube:  YouTube Data API v3 (official) → SerpAPI YouTube fallback
No AI tokens consumed — pure HTTP.
"""
import os
import logging
import re
import time
import json
import requests
import requests.auth
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# SerpAPI keys (YouTube fallback only) — read from env, fallback to hardcoded
_SERPAPI_KEYS = [k for k in [
    os.environ.get("SERPAPI_KEY", "36ecdeaea18fef34551d42aadb0dcd031df2737b6ccc320460ea762a4d0271fc"),
    os.environ.get("SERPAPI_KEY_2", "646f6e87520dd1866a7d16772217927008e849596207fab35437e25654338393"),
] if k]

# Cache the versioned embed_loader.js URL (changes infrequently)
_embed_loader_cache: dict = {"url": "", "ts": 0.0}

# Official YouTube Data API v3 — read from env, fallback to hardcoded
_YT_KEY = os.environ.get("YT_KEY", "AIzaSyCQonRHJK44tgtwcacowpcEBWcl_iYCZ2E")

# Official Reddit API (application-only OAuth) — read from env, fallback to hardcoded
_REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", "8kghbyl5acamAzbpICzpEg")
_REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "zJM7Q8R_QaDJQCau7hqnL50FhhrlAg")
_REDDIT_UA = "FlipAFind/1.0 (resale research tool)"


# ─── Google Trends ──────────────────────────────────────────────────────────

def get_trend_data(keyword: str) -> dict:
    """Return {keyword, embed_url} so the template can render the real Google Trends widget."""
    if not keyword or not keyword.strip():
        return {}
    embed_url = _get_embed_loader_url()
    if not embed_url:
        return {}
    return {"keyword": keyword, "embed_url": embed_url}


def _head_check(url: str) -> tuple:
    try:
        r = requests.head(url, timeout=4)
        return r.status_code == 200, url
    except Exception:
        return False, url


def _get_embed_loader_url() -> str:
    """
    Find and cache the versioned Google Trends embed_loader.js URL.
    Strategy:
      1. Try the embed explore endpoint (more likely to contain the URL in HTML).
      2. Parallel HEAD checks on a range of plausible version numbers.
    Cached for 24 hours.
    """
    global _embed_loader_cache
    now = time.time()
    if _embed_loader_cache["url"] and (now - _embed_loader_cache["ts"]) < 86400:
        return _embed_loader_cache["url"]

    _UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")

    # Method 1: parse from Google Trends embed endpoint
    req_param = json.dumps({
        "comparisonItem": [{"keyword": "shoes", "geo": "", "time": "today 12-m"}],
        "category": 0, "property": ""
    })
    for url_to_try in [
        f"https://trends.google.com/trends/embed/explore/TIMESERIES?req={requests.utils.quote(req_param)}&tz=0&hl=en-US",
        "https://trends.google.com/trends/explore?q=shoes&date=today+12-m",
    ]:
        try:
            resp = requests.get(url_to_try, headers={"User-Agent": _UA}, timeout=10)
            match = re.search(
                r'https://ssl\.gstatic\.com/trends_nrtr/([^"\']+)/embed_loader\.js',
                resp.text,
            )
            if match:
                url = f"https://ssl.gstatic.com/trends_nrtr/{match.group(1)}/embed_loader.js"
                _embed_loader_cache = {"url": url, "ts": now}
                logger.info(f"Google Trends embed_loader (parsed): {url}")
                return url
        except Exception as e:
            logger.warning(f"Embed page fetch failed ({url_to_try}): {e}")

    # Method 2: parallel HEAD checks on plausible version numbers
    # Version increments ~40-80/month; 3826 known late-2025 → ~4200 by mid-2026
    candidates = [
        f"https://ssl.gstatic.com/trends_nrtr/{ver}_{rc}/embed_loader.js"
        for ver in range(4400, 3700, -40)
        for rc in ("RC01", "RC00")
    ]
    found_url = None
    with ThreadPoolExecutor(max_workers=15) as ex:
        futures = {ex.submit(_head_check, u): u for u in candidates}
        for future in as_completed(futures):
            ok, url = future.result()
            if ok:
                found_url = url
                break

    if found_url:
        _embed_loader_cache = {"url": found_url, "ts": now}
        logger.info(f"Google Trends embed_loader (HEAD): {found_url}")
        return found_url

    logger.warning("Could not determine Google Trends embed_loader.js URL")
    return ""


# ─── Social Data ─────────────────────────────────────────────────────────────

def get_social_data(keyword: str) -> dict:
    """Return {reddit: [...], youtube: [...]} or {} on failure."""
    if not keyword or not keyword.strip():
        return {}

    result = {"reddit": [], "youtube": []}

    # Trim to first 4 words for Reddit — full product descriptions return irrelevant posts
    reddit_keyword = " ".join(keyword.split()[:4])

    # Reddit: official OAuth API first, free public JSON as fallback
    result["reddit"] = _try_reddit_oauth(reddit_keyword)
    if not result["reddit"]:
        result["reddit"] = _try_reddit_public(reddit_keyword)

    # YouTube: official Data API v3 first, SerpAPI as fallback
    result["youtube"] = _try_youtube_official(keyword)
    if not result["youtube"]:
        for key in _SERPAPI_KEYS:
            result["youtube"] = _try_youtube_serpapi(keyword, key)
            if result["youtube"]:
                break

    return result if (result["reddit"] or result["youtube"]) else {}


def _try_reddit_oauth(keyword: str) -> list:
    """Reddit application-only OAuth (no user login required)."""
    try:
        # Step 1: Get access token
        token_resp = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=requests.auth.HTTPBasicAuth(_REDDIT_CLIENT_ID, _REDDIT_CLIENT_SECRET),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": _REDDIT_UA},
            timeout=8,
        )
        if token_resp.status_code != 200:
            logger.warning(f"Reddit OAuth token HTTP {token_resp.status_code}: {token_resp.text[:200]}")
            return []
        access_token = token_resp.json().get("access_token")
        if not access_token:
            logger.warning("Reddit OAuth: no access_token in response")
            return []

        # Step 2: Search
        search_resp = requests.get(
            "https://oauth.reddit.com/search",
            params={"q": keyword, "sort": "relevance", "limit": 5, "type": "link"},
            headers={
                "User-Agent": _REDDIT_UA,
                "Authorization": f"bearer {access_token}",
            },
            timeout=8,
        )
        if search_resp.status_code != 200:
            logger.warning(f"Reddit OAuth search HTTP {search_resp.status_code}: {search_resp.text[:200]}")
            return []

        children = search_resp.json().get("data", {}).get("children", [])
        posts = []
        for child in children[:5]:
            d = child.get("data", {})
            snippet = (d.get("selftext") or "")[:200]
            posts.append({
                "title": d.get("title", ""),
                "link": f"https://www.reddit.com{d.get('permalink', '')}",
                "snippet": snippet,
                "subreddit": d.get("subreddit_name_prefixed", ""),
            })
        logger.info(f"Reddit OAuth: {len(posts)} posts for '{keyword}'")
        return posts
    except Exception as e:
        logger.warning(f"Reddit OAuth exception for '{keyword}': {e}")
        return []


def _try_reddit_public(keyword: str) -> list:
    """Reddit free public JSON search — no auth required."""
    try:
        resp = requests.get(
            "https://www.reddit.com/search.json",
            params={"q": keyword, "sort": "relevance", "limit": 5, "type": "link"},
            headers={"User-Agent": _REDDIT_UA},
            timeout=8,
        )
        if resp.status_code != 200:
            logger.warning(f"Reddit public HTTP {resp.status_code} for '{keyword}'")
            return []
        children = resp.json().get("data", {}).get("children", [])
        posts = []
        for child in children[:5]:
            d = child.get("data", {})
            snippet = (d.get("selftext") or "")[:200]
            posts.append({
                "title": d.get("title", ""),
                "link": f"https://www.reddit.com{d.get('permalink', '')}",
                "snippet": snippet,
                "subreddit": d.get("subreddit_name_prefixed", ""),
            })
        logger.info(f"Reddit public: {len(posts)} posts for '{keyword}'")
        return posts
    except Exception as e:
        logger.warning(f"Reddit public exception for '{keyword}': {e}")
        return []


def _try_youtube_official(keyword: str) -> list:
    """YouTube Data API v3 search."""
    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": keyword,
                "maxResults": 4,
                "type": "video",
                "key": _YT_KEY,
            },
            timeout=8,
        )
        if resp.status_code != 200:
            logger.warning(f"YouTube API HTTP {resp.status_code} for '{keyword}': {resp.text[:200]}")
            return []
        items = resp.json().get("items", [])
        videos = []
        for item in items[:4]:
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId", "")
            thumbnail = (
                snippet.get("thumbnails", {}).get("medium", {}).get("url", "")
                or snippet.get("thumbnails", {}).get("default", {}).get("url", "")
            )
            videos.append({
                "title": snippet.get("title", ""),
                "link": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail": thumbnail,
                "channel": snippet.get("channelTitle", ""),
                "views": "",
            })
        logger.info(f"YouTube API: {len(videos)} videos for '{keyword}'")
        return videos
    except Exception as e:
        logger.warning(f"YouTube API exception for '{keyword}': {e}")
        return []


def _try_youtube_serpapi(keyword: str, api_key: str) -> list:
    try:
        resp = requests.get(
            "https://serpapi.com/search.json",
            params={"engine": "youtube", "search_query": keyword, "api_key": api_key},
            timeout=8,
        )
        if resp.status_code != 200:
            logger.warning(f"SerpAPI YouTube HTTP {resp.status_code} for '{keyword}': {resp.text[:200]}")
            return []
        results = resp.json().get("video_results", [])
        videos = []
        for v in results[:4]:
            videos.append({
                "title": v.get("title", ""),
                "link": v.get("link", ""),
                "thumbnail": v.get("thumbnail", {}).get("static", ""),
                "channel": v.get("channel", {}).get("name", ""),
                "views": v.get("views", ""),
            })
        return videos
    except Exception as e:
        logger.warning(f"SerpAPI YouTube exception for '{keyword}': {e}")
        return []
