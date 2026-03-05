import os
import io
import base64
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_gemini_client = None
_groq_client = None

# Model preference order — best first
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash"]


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


def _call_gemini(model: str, parts: list, use_search: bool) -> str:
    client = _get_gemini_client()
    config_kwargs = {"max_output_tokens": 1500, "temperature": 0.2}
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
    return " ".join(text_parts).strip()


def _call_groq(prompt_text: str) -> str:
    client = _get_groq_client()
    logger.info("Using Groq llama-3.3-70b as fallback")
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt_text}],
        max_tokens=1500,
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()


def run_with_search(prompt: str, image_base64: str = None,
                    image_media_type: str = None, use_search: bool = True) -> str:
    """
    Fallback chain: gemini-2.5-flash → gemini-2.5-flash-lite → gemini-1.5-flash → Groq
    Each model uses the correct search tool for its generation.
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

    for model in GEMINI_MODELS:
        for attempt_search in ([True, False] if use_search else [False]):
            try:
                result = _call_gemini(model, parts, attempt_search)
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
