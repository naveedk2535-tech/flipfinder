import os
import io
import base64
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_client = None

# Model preference order — tries best first, falls back automatically
MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash"]


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get('GEMINI_API_KEY', '')
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        _client = genai.Client(api_key=api_key)
    return _client


def _call_model(model: str, parts: list, use_search: bool) -> str:
    """Attempt a single model call. Raises on failure."""
    client = _get_client()

    config_kwargs = {
        "max_output_tokens": 1500,
        "temperature": 0.2,
    }

    if use_search:
        config_kwargs["tools"] = [
            types.Tool(
                google_search_retrieval=types.GoogleSearchRetrieval(
                    dynamic_retrieval_config=types.DynamicRetrievalConfig(
                        mode=types.DynamicRetrievalConfigMode.MODE_DYNAMIC,
                        dynamic_threshold=0.3
                    )
                )
            )
        ]

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
    return " ".join(text_parts).strip()


def run_with_search(prompt: str, image_base64: str = None,
                    image_media_type: str = None, use_search: bool = True) -> str:
    """
    Call Gemini with Google Search grounding and optional image support.
    Tries models in order: gemini-2.5-flash → gemini-2.5-flash-lite → gemini-1.5-flash
    Automatically falls back if a model returns 429 or quota error.
    Free tier: 1500 req/day on 1.5-flash minimum.
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

    # Try each model in preference order
    last_error = None
    for model in MODELS:
        try:
            result = _call_model(model, parts, use_search)
            if result:
                logger.info(f"Success with model: {model}")
                return result
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                logger.warning(f"{model} quota exceeded, trying next model...")
                last_error = e
                continue
            # Non-quota error — try without search then give up
            if use_search:
                logger.warning(f"{model} error with search, retrying without: {e}")
                try:
                    client = _get_client()
                    response = client.models.generate_content(
                        model=model,
                        contents=parts,
                        config=types.GenerateContentConfig(
                            max_output_tokens=1500,
                            temperature=0.2
                        )
                    )
                    text_parts = [
                        part.text for candidate in response.candidates
                        for part in candidate.content.parts
                        if hasattr(part, 'text') and part.text
                    ]
                    result = " ".join(text_parts).strip()
                    if result:
                        return result
                except Exception as e2:
                    last_error = e2
                    continue
            last_error = e
            continue

    raise ValueError(f"All Gemini models failed. Last error: {last_error}")
