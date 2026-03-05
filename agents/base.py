import os
import anthropic
import logging

logger = logging.getLogger(__name__)


def run_with_search(prompt: str, image_base64: str = None,
                    image_media_type: str = None, use_search: bool = True) -> str:
    """Call Claude claude-sonnet-4-5 with optional web search and optional image."""
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    if image_base64:
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image_media_type or "image/jpeg",
                    "data": image_base64
                }
            },
            {"type": "text", "text": prompt}
        ]
    else:
        content = prompt

    kwargs = dict(
        model="claude-sonnet-4-5",
        max_tokens=1500,
        messages=[{"role": "user", "content": content}]
    )

    if use_search:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search"}]

    response = client.messages.create(**kwargs)
    full_text = " ".join([
        block.text for block in response.content
        if hasattr(block, "text")
    ])
    return full_text.strip()
