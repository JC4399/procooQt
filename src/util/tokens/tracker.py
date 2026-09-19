"""Per-session token and size accounting for Agent."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from .counter import count_content_tokens, count_tokens


class SessionTokenTracker:
    """Tracks system-prompt tokens and computes session token/byte totals.

    Attributes:
        sys_prompt_tokens: Cached word-count estimate of the system prompt.
    """

    def __init__(self, sys_prompt: str) -> None:
        """Initialize the tracker with the system prompt.

        Args:
            sys_prompt: The system prompt string to cache tokens for.
        """
        self.sys_prompt_tokens: int = count_tokens(sys_prompt)

    def update_sys_prompt(self, sys_prompt: str) -> None:
        """Recache system-prompt token count after prompt mutations.

        Args:
            sys_prompt: New system prompt string.
        """
        self.sys_prompt_tokens = count_tokens(sys_prompt)

    def compute_total(self, messages: list[dict[str, Any]]) -> int:
        """Estimate total session tokens from messages + cached system prompt.

        Args:
            messages: List of OpenAI-compatible message dicts (``role``,
                ``content``, ``tool_calls``, etc.).

        Returns:
            Estimated total token count.
        """
        total = self.sys_prompt_tokens
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, (str, list)):
                total += count_content_tokens(content)
            for tc in msg.get("tool_calls", []):
                fn = tc.get("function", {})
                total += count_tokens(fn.get("name", "") + fn.get("arguments", ""))
        return total

    def compute_bytes(self, messages: list[dict[str, Any]]) -> int:
        """Compute the JSON byte size of the message history.

        Args:
            messages: List of OpenAI-compatible message dicts.

        Returns:
            Byte size of the serialized message list (UTF-8).
        """
        return len(json.dumps(messages, ensure_ascii=False, default=str).encode("utf-8"))

    # ------------------------------------------------------------------
    #  Async (offloaded) variants — never block the UI event loop
    # ------------------------------------------------------------------

    async def compute_total_async(self, messages: list[dict[str, Any]]) -> int:
        """Offloaded variant of :meth:`compute_total`."""
        return await asyncio.to_thread(self.compute_total, messages)

    async def compute_bytes_async(self, messages: list[dict[str, Any]]) -> int:
        """Offloaded variant of :meth:`compute_bytes`."""
        return await asyncio.to_thread(self.compute_bytes, messages)
