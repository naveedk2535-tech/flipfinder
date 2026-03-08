import os
import re
import json
import base64
import logging
import threading
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)
_clients_lock = threading.Lock()


def _close_json(partial: str) -> str:
    """
    Close any open strings and brackets in a truncated JSON fragment.
    Tracks bracket stack and string state to produce syntactically valid JSON.
    Also strips trailing commas (from truncation mid-list/object).
    """
    stack = []
    in_str = False
    escaped = False
    for ch in partial:
        if escaped:
            escaped = False
        elif ch == '\\':
            escaped = True
        elif ch == '"':
            in_str = not in_str
        elif not in_str:
            if ch in '{[':
                stack.append('}' if ch == '{' else ']')
            elif ch in '}]' and stack:
                stack.pop()

    if in_str:
        # Close the open string, then close brackets
        suffix = '"' + ''.join(reversed(stack))
        return partial + suffix
    else:
        # Strip trailing comma/whitespace before closing (truncated mid-list/object)
        trimmed = partial.rstrip()
        if trimmed.endswith(','):
            trimmed = trimmed[:-1]
        suffix = ''.join(reversed(stack))
        return trimmed + suffix


def parse_first_json(raw: str):
    """
    Extract and parse the first complete JSON object from a raw string.
    Strategy:
      1. Strip ONLY the outer markdown code fence (leading/trailing).
      2. Direct parse.
      3. If embedded ``` fences remain (search-result contamination), truncate there
         and close the JSON algorithmically — preserves all fields before the corruption.
      4. Fix unescaped newlines inside string values.
      5. Trim-from-end fallback.
    """
    # Strip ONLY leading and trailing fences (not ones embedded inside values)
    cleaned = re.sub(r'^\s*```(?:json|JSON)?\s*\n?', '', raw.strip())
    cleaned = re.sub(r'\s*```\s*$', '', cleaned.strip())

    for text in [cleaned, raw]:
        start = text.find('{')
        if start < 0:
            continue
        fragment = text[start:]

        # Pass 1: direct parse
        try:
            obj, _ = json.JSONDecoder().raw_decode(fragment, 0)
            return obj
        except json.JSONDecodeError:
            pass

        # Pass 2: embedded fence detected — truncate and algorithmically close
        fence_pos = fragment.find('```')
        if fence_pos > 0:
            closed = _close_json(fragment[:fence_pos])
            try:
                obj, _ = json.JSONDecoder().raw_decode(closed, 0)
                return obj
            except (json.JSONDecodeError, Exception):
                pass

        # Pass 2b: algorithmically close any truncated JSON (no fence needed)
        closed = _close_json(fragment)
        if closed != fragment:
            try:
                obj, _ = json.JSONDecoder().raw_decode(closed, 0)
                return obj
            except (json.JSONDecodeError, Exception):
                pass

        # Pass 2c: strip to last complete field (handles truncation inside a key name)
        last_safe = -1
        p_in_str, p_esc = False, False
        for i, ch in enumerate(fragment):
            if p_esc: p_esc = False
            elif ch == '\\': p_esc = True
            elif ch == '"': p_in_str = not p_in_str
            elif not p_in_str and ch in ',{[':
                last_safe = i
        if last_safe > 0:
            closed_partial = _close_json(fragment[:last_safe])
            try:
                obj, _ = json.JSONDecoder().raw_decode(closed_partial, 0)
                return obj
            except (json.JSONDecodeError, Exception):
                pass

        # Pass 3: fix unescaped newlines inside JSON string values
        try:
            fixed = []
            in_str = False
            escaped = False
            for ch in fragment:
                if escaped:
                    fixed.append(ch)
                    escaped = False
                elif ch == '\\':
                    fixed.append(ch)
                    escaped = True
                elif ch == '"':
                    fixed.append(ch)
                    in_str = not in_str
                elif in_str and ch == '\n':
                    fixed.append(' ')
                elif in_str and ch == '\r':
                    pass
                else:
                    fixed.append(ch)
            obj, _ = json.JSONDecoder().raw_decode(''.join(fixed), 0)
            return obj
        except (json.JSONDecodeError, Exception):
            pass

        # Pass 4: trim from end until valid
        end = fragment.rfind('}')
        while end > 0:
            try:
                return json.loads(fragment[:end + 1])
            except json.JSONDecodeError:
                end = fragment.rfind('}', 0, end)

    return None


def _add_tokens(count: int):
    """Accumulate token usage in Flask request context if available."""
    try:
        from flask import g
        g.tokens_used = getattr(g, 'tokens_used', 0) + count
    except RuntimeError:
        pass  # Outside Flask context (e.g. testing)


def _track(api: str, key_label: str, *, success: bool, quota_hit: bool, tokens: int = 0):
    try:
        from utils.api_tracker import record
        record(api, key_label, success=success, quota_hit=quota_hit, tokens=tokens)
    except Exception:
        pass


# Lazily-initialised client list — one entry per API key found in env
_gemini_clients = None
_groq_clients = None

# Model preference order — 2.0-flash first: no thinking tokens = faster, same search quality, 3× higher RPD quota
# Per-model free-tier RPD: 2.0-flash=1500, 2.5-flash=500, 2.5-flash-lite=500, 2.0-flash-lite=1500
GEMINI_MODELS = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash-lite"]
# Lighter chain for simple tasks (extraction, arbitrage)
GEMINI_FAST_MODELS = ["gemini-2.0-flash-lite", "gemini-2.5-flash-lite", "gemini-2.0-flash"]


def _get_gemini_clients():
    """Return list of Gemini clients, one per API key set in env (KEY + KEY_2)."""
    global _gemini_clients
    if _gemini_clients is None:
        with _clients_lock:
            if _gemini_clients is None:  # double-check inside lock
                clients = []
                for var in ('GEMINI_API_KEY', 'GEMINI_API_KEY_2'):
                    key = os.environ.get(var, '').strip()
                    if key:
                        clients.append(genai.Client(api_key=key))
                        logger.info(f"Gemini client loaded from {var}")
                if not clients:
                    raise ValueError("No GEMINI_API_KEY set")
                _gemini_clients = clients
    return _gemini_clients


def _get_groq_clients():
    """Return list of Groq clients, one per API key set in env (KEY + KEY_2)."""
    global _groq_clients
    if _groq_clients is None:
        with _clients_lock:
            if _groq_clients is None:  # double-check inside lock
                from groq import Groq
                clients = []
                for var in ('GROQ_API_KEY', 'GROQ_API_KEY_2'):
                    key = os.environ.get(var, '').strip()
                    if key:
                        clients.append(Groq(api_key=key))
                        logger.info(f"Groq client loaded from {var}")
                if not clients:
                    raise ValueError("No GROQ_API_KEY set")
                _groq_clients = clients
    return _groq_clients


def _search_tool_for(model: str):
    """
    gemini-1.5-x  → google_search_retrieval (old API)
    gemini-2.0-x+ → google_search (new API)
    """
    if "1.5" in model:
        return types.Tool(
            google_search_retrieval=types.GoogleSearchRetrieval(
                dynamic_retrieval_config=types.DynamicRetrievalConfig(
                    mode=types.DynamicRetrievalConfigMode.MODE_DYNAMIC,
                    dynamic_threshold=0.3
                )
            )
        )
    else:
        return types.Tool(google_search=types.GoogleSearch())


def _call_gemini(client, model: str, parts: list, use_search: bool, max_tokens: int = 4096) -> str:
    config_kwargs = {"max_output_tokens": max_tokens, "temperature": 0.2}
    # Disable thinking on 2.5-flash models — eliminates 20-30s hidden latency, no quality loss for JSON tasks
    if "2.5" in model:
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
    if use_search:
        config_kwargs["tools"] = [_search_tool_for(model)]
        config_kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(
            maximum_remote_calls=5
        )

    response = client.models.generate_content(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(**config_kwargs)
    )
    text_parts = [
        part.text for candidate in response.candidates
        if candidate.content and candidate.content.parts
        for part in candidate.content.parts
        if hasattr(part, 'text') and part.text
    ]
    try:
        if response.usage_metadata:
            _add_tokens(response.usage_metadata.total_token_count or 0)
    except Exception:
        pass
    return "".join(text_parts).strip()


def _call_groq(client, prompt_text: str, max_tokens: int = 4096) -> str:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt_text}],
        max_tokens=max_tokens,
        temperature=0.2,
    )
    try:
        _add_tokens(response.usage.total_tokens or 0)
    except Exception:
        pass
    return response.choices[0].message.content.strip()


def run_with_search(prompt: str, image_base64: str = None,
                    image_media_type: str = None, use_search: bool = True,
                    max_tokens: int = 4096, fast: bool = False) -> str:
    """
    Fallback chain: for each model, try every Gemini API key before moving on.
    Key rotation doubles available free quota when GEMINI_API_KEY_2 is set.
    fast=True skips expensive full flash (used for extraction/arbitrage).
    max_tokens is forwarded to both Gemini and Groq to avoid wasted tokens.
    """
    parts = []
    if image_base64:
        try:
            image_bytes = base64.b64decode(image_base64)
            parts.append(types.Part.from_bytes(
                data=image_bytes,
                mime_type=image_media_type or "image/jpeg"
            ))
        except Exception as e:
            logger.warning(f"Image decode error: {e}")
    parts.append(types.Part.from_text(text=prompt))

    models = GEMINI_FAST_MODELS if fast else GEMINI_MODELS
    clients = _get_gemini_clients()

    for model in models:
        for key_idx, client in enumerate(clients):
            key_label = f"key{key_idx + 1}"
            for attempt_search in ([True, False] if use_search else [False]):
                try:
                    result = _call_gemini(client, model, parts, attempt_search, max_tokens=max_tokens)
                    if result:
                        logger.info(f"Gemini success: {model} ({key_label}, search={attempt_search})")
                        _track('gemini', key_label, success=True, quota_hit=False)
                        return result
                except Exception as e:
                    err = str(e)
                    is_quota = "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower()
                    if is_quota:
                        logger.warning(f"{model} {key_label} quota exceeded, trying next...")
                        _track('gemini', key_label, success=False, quota_hit=True)
                        break  # try next key (or next model if no more keys)
                    elif attempt_search:
                        logger.warning(f"{model} {key_label} search error, retrying without: {e}")
                        continue  # retry without search on same key
                    else:
                        logger.warning(f"{model} {key_label} failed: {e}")
                        _track('gemini', key_label, success=False, quota_hit=False)
                        break  # try next key

    # Final fallback: Groq with key rotation
    groq_clients = _get_groq_clients()
    last_err = None
    for g_idx, groq_client in enumerate(groq_clients):
        try:
            logger.info(f"Using Groq llama-3.3-70b as fallback (key{g_idx + 1})")
            result = _call_groq(groq_client, prompt, max_tokens=max_tokens)
            _track('groq', f'key{g_idx + 1}', success=True, quota_hit=False)
            return result
        except Exception as e:
            err = str(e)
            is_quota = "429" in err or "rate_limit" in err.lower() or "quota" in err.lower()
            logger.error(f"Groq key{g_idx + 1} failed: {e}")
            _track('groq', f'key{g_idx + 1}', success=False, quota_hit=is_quota)
            last_err = e
            if is_quota:
                continue  # try next Groq key
            break  # non-quota error, don't bother retrying
    raise ValueError(f"All AI providers failed. Last error: {last_err}")
