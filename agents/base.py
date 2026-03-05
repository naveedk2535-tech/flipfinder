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
    Call Gemini 2.0 Flash with:
    - Native Google Search grounding (real-time web results, no extra cost)
    - Native image understanding (photo → full product analysis)
    - Free tier: 1500 requests/day, 1M tokens/minute
    """
    client = _get_client()

    # Build content parts
    parts = []

    # Image support — Gemini 2.0 Flash reads images natively
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

    # Config with optional Google Search grounding
    tool_list = []
    if use_search:
        tool_list = [types.Tool(google_search=types.GoogleSearch())]

    config = types.GenerateContentConfig(
        max_output_tokens=1500,
        temperature=0.2,
        tools=tool_list if tool_list else None
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=parts,
            config=config
        )
        # Extract text — response may include grounding chunks alongside text
        text_parts = []
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if hasattr(part, 'text') and part.text:
                    text_parts.append(part.text)
        return " ".join(text_parts).strip()

    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        # Retry without search if search caused the failure
        if tool_list:
            logger.info("Retrying without search tools...")
            config_no_search = types.GenerateContentConfig(
                max_output_tokens=1500,
                temperature=0.2
            )
            response = client.models.generate_content(
                model="gemini-2.0-flash",
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
