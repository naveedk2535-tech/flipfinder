import os
import io
import base64
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get('GEMINI_API_KEY', '')
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        _client = genai.Client(api_key=api_key)
    return _client


def run_with_search(prompt: str, image_base64: str = None,
                    image_media_type: str = None, use_search: bool = True) -> str:
    """
    Call Gemini 1.5 Flash (free tier: 1500 req/day) with:
    - Google Search grounding for live price/market research
    - Native image understanding for product photos
    """
    client = _get_client()

    # Build content parts
    parts = []

    # Image support — Gemini 1.5 Flash reads images natively
    if image_base64:
        try:
            image_bytes = base64.b64decode(image_base64)
            parts.append(
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=image_media_type or "image/jpeg"
                )
            )
        except Exception as e:
            logger.warning(f"Image decode error: {e}")

    parts.append(types.Part.from_text(text=prompt))

    # Google Search grounding for gemini-1.5-flash uses google_search_retrieval
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

    config = types.GenerateContentConfig(**config_kwargs)

    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=parts,
            config=config
        )
        text_parts = []
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if hasattr(part, 'text') and part.text:
                    text_parts.append(part.text)
        result = " ".join(text_parts).strip()
        if not result:
            result = response.text
        return result

    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        # Retry without search if search caused the failure
        if use_search:
            logger.info("Retrying without search tools...")
            config_no_search = types.GenerateContentConfig(
                max_output_tokens=1500,
                temperature=0.2
            )
            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=parts,
                config=config_no_search
            )
            text_parts = []
            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if hasattr(part, 'text') and part.text:
                        text_parts.append(part.text)
            return " ".join(text_parts).strip()
        raise
