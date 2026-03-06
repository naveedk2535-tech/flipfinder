import os
import io
import json
import base64
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


def parse_first_json(raw: str):
    """
    Extract and parse the first complete JSON object from a raw string.
    Handles cases where the AI wraps JSON in markdown fences or appends extra text.
    """
    start = raw.find('{')
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(raw, start)
        return obj
    except json.JSONDecodeError:
        # Fallback: try trimming end until valid
        end = raw.rfind('}')
        while end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                end = raw.rfind('}', start, end)
        return None


def _add_tokens(count: int):
    """Accumulate token usage in Flask request context if available."""
    try:
        from flask import g
        g.tokens_used = getattr(g, 'tokens_used', 0) + count
    except RuntimeError:
        pass  # Outside Flask context (e.g. testing)

_gemini_client = None
_groq_client = None

# Model preference order — best first
# gemini-1.5-flash is deprecated (404) — replaced with gemini-2.0-flash-lite
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash-lite"]
# Lighter chain for simple tasks (extraction, arbitrage) — skips full flash to save quota
GEMINI_FAST_MODELS = ["gemini-2.5-flash-lite", "gemini-2.0-flash-lite"]


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        api_key = os.environ.get('GEMINI_API_KEY', '')
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        api_key = os.environ.get('GROQ_API_KEY', '')
        if not api_key:
            raise ValueError("GROQ_API_KEY not set")
        _groq_client = Groq(api_key=api_key)
    return _groq_client


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


def _call_gemini(model: str, parts: list, use_search: bool, max_tokens: int = 8192) -> str:
    client = _get_gemini_client()
    config_kwargs = {"max_output_tokens": max_tokens, "temperature": 0.2}
    if use_search:
        config_kwargs["tools"] = [_search_tool_for(model)]

    response = client.models.generate_content(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(**config_kwargs)
    )
    text_parts = [
        part.text for candidate in response.candidates
        for part in candidate.content.parts
        if hasattr(part, 'text') and part.text
    ]
    # Track token usage
    try:
        if response.usage_metadata:
            _add_tokens(response.usage_metadata.total_token_count or 0)
    except Exception:
        pass
    return " ".join(text_parts).strip()


def _call_groq(prompt_text: str) -> str:
    client = _get_groq_client()
    logger.info("Using Groq llama-3.3-70b as fallback")
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt_text}],
        max_tokens=8192,
        temperature=0.2,
    )
    try:
        _add_tokens(response.usage.total_tokens or 0)
    except Exception:
        pass
    return response.choices[0].message.content.strip()


def run_with_search(prompt: str, image_base64: str = None,
                    image_media_type: str = None, use_search: bool = True,
                    max_tokens: int = 8192, fast: bool = False) -> str:
    """
    Fallback chain: gemini-2.5-flash → gemini-2.5-flash-lite → gemini-2.0-flash-lite → Groq
    fast=True skips full flash and starts with flash-lite (for extraction/arbitrage).
    max_tokens controls per-call output limit.
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
    for model in models:
        for attempt_search in ([True, False] if use_search else [False]):
            try:
                result = _call_gemini(model, parts, attempt_search, max_tokens=max_tokens)
                if result:
                    logger.info(f"Gemini success: {model} (search={attempt_search})")
                    return result
            except Exception as e:
                err = str(e)
                is_quota = "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower()
                if is_quota:
                    logger.warning(f"{model} quota exceeded, trying next model...")
                    break
                elif attempt_search:
                    logger.warning(f"{model} search error, retrying without: {e}")
                    continue
                else:
                    logger.warning(f"{model} failed: {e}")
                    break

    # Final fallback: Groq
    try:
        return _call_groq(prompt)
    except Exception as e:
        logger.error(f"Groq fallback failed: {e}")
        raise ValueError(f"All AI providers failed. Last error: {e}")
