"""Token estimation via word count — no external tokenizer."""

from __future__ import annotations

import math
from typing import Any

# Approximate number of words per token for the word-count estimate.
# ``tokens = ceil(words / WORDS_PER_TOKEN)`` (~1.33 tokens per word).
WORDS_PER_TOKEN = 0.75

# Flat token budget attributed to each image part when estimating multimodal content.
IMAGE_TOKEN_ESTIMATE = 1024


def count_tokens(text: str) -> int:
    """Estimate the token count of a plain-text string by word count.

    Args:
        text: Plain text to estimate.

    Returns:
        Estimated token count (0 for empty text).
    """
    if not text:
        return 0
    words = len(text.split())
    return max(1, math.ceil(words / WORDS_PER_TOKEN))


def count_content_tokens(content: Any) -> int:
    """Estimate tokens for message content (str or list of content parts).

    Handles plain strings and OpenAI-style multimodal content lists
    (``{"type": "text", "text": ...}`` / ``{"type": "image_url", ...}``).

    Args:
        content: Message content (string or list of part dicts).

    Returns:
        Estimated token count.
    """
    if isinstance(content, str):
        return count_tokens(content)

    if not isinstance(content, list):
        return 0

    total = 0
    for part in content:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type", "")
        if part_type == "text":
            total += count_tokens(part.get("text", ""))
        elif part_type == "image_url":
            total += IMAGE_TOKEN_ESTIMATE
    return total
