"""
Thread-safe daily API usage counter.

Limits reset at midnight Pacific (UTC-8 / UTC-7 DST) for Google/Groq.
We approximate using UTC midnight as the reset boundary, which is close enough
for monitoring purposes. Each day's data is keyed by UTC date string YYYY-MM-DD.

Data stored in api_usage_log.json next to this file.
"""
import json
import os
import threading
from datetime import datetime, timezone, timedelta

_lock = threading.Lock()

# Store next to the utils package
_LOG_FILE = os.path.join(os.path.dirname(__file__), '..', 'api_usage_log.json')

# Known daily limits (free tier)
LIMITS = {
    'gemini/key1': {'label': 'Gemini key1', 'rpm': 15,  'rpd': 1500, 'note': 'Combined across all models'},
    'gemini/key2': {'label': 'Gemini key2', 'rpm': 15,  'rpd': 1500, 'note': 'Combined across all models'},
    'groq/key1':   {'label': 'Groq key1',   'rpm': 30,  'rpd': 14400, 'note': 'llama-3.3-70b'},
    'groq/key2':   {'label': 'Groq key2',   'rpm': 30,  'rpd': 14400, 'note': 'llama-3.3-70b'},
    'serpapi/key1':{'label': 'SerpAPI key1','rpm': None, 'rpd': None,  'note': '100/mo free or paid'},
    'serpapi/key2':{'label': 'SerpAPI key2','rpm': None, 'rpd': None,  'note': '100/mo free or paid'},
    'youtube/key1':{'label': 'YouTube API', 'rpm': None, 'rpd': 10000, 'note': 'units/day'},
    'reddit/oauth':{'label': 'Reddit OAuth','rpm': 60,   'rpd': None,  'note': 'requests/min'},
}


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def _load() -> dict:
    try:
        with open(_LOG_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict):
    try:
        with open(_LOG_FILE, 'w') as f:
            json.dump(data, f)
    except Exception:
        pass


def record(api: str, key_label: str, *, success: bool, quota_hit: bool, tokens: int = 0):
    """Record one API call outcome.

    api       — e.g. 'gemini', 'groq', 'serpapi', 'youtube', 'reddit'
    key_label — e.g. 'key1', 'key2', 'oauth'
    """
    today = _today_utc()
    slot = f"{api}/{key_label}"
    with _lock:
        data = _load()
        day = data.setdefault(today, {})
        entry = day.setdefault(slot, {
            'calls': 0, 'successes': 0, 'quota_hits': 0, 'tokens': 0
        })
        entry['calls'] += 1
        if success:
            entry['successes'] += 1
        if quota_hit:
            entry['quota_hits'] += 1
        entry['tokens'] += tokens
        _save(data)


def get_today_stats() -> dict:
    """Return today's stats merged with limit metadata."""
    today = _today_utc()
    data = _load()
    today_data = data.get(today, {})

    result = {}
    for slot, meta in LIMITS.items():
        entry = today_data.get(slot, {'calls': 0, 'successes': 0, 'quota_hits': 0, 'tokens': 0})
        rpd = meta['rpd']
        pct = round((entry['calls'] / rpd * 100), 1) if rpd and entry['calls'] else 0
        result[slot] = {
            **meta,
            **entry,
            'rpd_limit': rpd,
            'pct_used': min(pct, 100),
            'near_limit': pct >= 70,
            'at_limit': pct >= 95 or entry['quota_hits'] > 0,
        }
    return result


def get_history(days: int = 7) -> list:
    """Return a list of {date, total_calls, total_quota_hits, total_tokens} for the last N days."""
    data = _load()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days - 1)).strftime('%Y-%m-%d')
    rows = []
    for date in sorted(data.keys()):
        if date < cutoff:
            continue
        day = data[date]
        total_calls = sum(e.get('calls', 0) for e in day.values())
        total_quota_hits = sum(e.get('quota_hits', 0) for e in day.values())
        total_tokens = sum(e.get('tokens', 0) for e in day.values())
        rows.append({
            'date': date,
            'calls': total_calls,
            'quota_hits': total_quota_hits,
            'tokens': total_tokens,
        })
    return rows
