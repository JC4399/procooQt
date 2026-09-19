"""OpenAI-compatible chat communication — types, formatting, and model client."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
from typing import TYPE_CHECKING, Any
import uuid

from json_repair import repair_json

logger = logging.getLogger("procoo_qt")

if TYPE_CHECKING:
    from openai import AsyncStream
    from openai.types.chat import ChatCompletion
else:
    ChatCompletion = "openai.types.chat.ChatCompletion"
    AsyncStream = "openai.types.chat.AsyncStream"


# ------------------------------------------------------------------
#  Chat response types
# ------------------------------------------------------------------


@dataclass
class ChatUsage:
    """Usage information for a chat model API invocation.

    Attributes:
        input_tokens: Number of prompt tokens consumed.
        output_tokens: Number of completion tokens generated.
        time: Wall-clock time in seconds for the API call.
    """

    input_tokens: int
    output_tokens: int
    time: float


@dataclass
class ChatResponse:
    """The response from a chat model.

    Attributes:
        content: List of content block dicts with ``"type"`` key
            (``"response"``, ``"thinking"``, or ``"tool_use"``).
        id: Unique response identifier.
        usage: Optional token usage and timing info.
        metadata: Optional arbitrary metadata dict.
    """

    content: list[dict]
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    usage: ChatUsage | None = None
    metadata: dict | None = None


# ------------------------------------------------------------------
#  OpenAI Chat Model
# ------------------------------------------------------------------


def _json_loads_with_repair(json_str: str) -> dict | list:
    """Repair and load a potentially incomplete JSON string into a dict or list."""
    try:
        repaired = repair_json(json_str, stream_stable=True)
        result = json.loads(repaired)
        if isinstance(result, (dict, list)):
            return result
    except Exception:
        if len(json_str) > 100:
            logger.warning("Failed to load JSON from: %s...", json_str[:100])
        else:
            logger.warning("Failed to load JSON from: %s", json_str)
    return {}


def _try_parse_json_dict(json_str: str) -> dict | list:
    """Attempt to parse a potentially incomplete JSON string into a dict or list."""
    json_str = json_str or "{}"
    try:
        result = json.loads(json_str)
        if isinstance(result, (dict, list)):
            return result
    except Exception:
        pass
    return {} if not json_str.strip() else _json_loads_with_repair(json_str)


class OpenAIChatModel:
    """OpenAI-compatible chat model client with streaming support.

    Handles text, thinking, and tool_use content blocks.  No audio/video
    support.  Only ``openai`` client type is supported.
    """

    def __init__(
        self,
        model_name: str,
        api_key: str | None = None,
        stream: bool = True,
        client_kwargs: dict[str, Any] | None = None,
        generate_kwargs: dict[str, Any] | None = None,
    ) -> None:
        """Initialise the chat model client.

        Args:
            model_name: The model identifier passed to the OpenAI API
                (e.g. ``"gpt-4"``).
            api_key: Optional API key.  If ``None``, the client uses
                the ``OPENAI_API_KEY`` environment variable.
            stream: Whether to use streaming responses by default.
            client_kwargs: Extra keyword arguments forwarded to
                ``openai.AsyncClient``.
            generate_kwargs: Extra keyword arguments merged into every
                completion request (e.g. ``temperature``, ``top_p``).
        """
        import openai

        self.model_name = model_name
        self.stream = stream
        self.generate_kwargs = generate_kwargs or {}
        self.client = openai.AsyncClient(
            api_key=api_key,
            **(client_kwargs or {}),
        )

    # ------------------------------------------------------------------
    #  Public: Invoke
    # ------------------------------------------------------------------

    async def __call__(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> ChatResponse | AsyncGenerator[ChatResponse]:
        """Invoke the chat completion API.

        Args:
            messages: OpenAI-formatted message dicts.
            tools: Optional list of function-calling tool schemas.
            tool_choice: Optional tool choice directive (``"auto"``,
                ``"none"``, ``"required"``, or a specific function name).
            **kwargs: Additional parameters forwarded to the API call.

        Returns:
            A ``ChatResponse`` for non-streaming calls, or an
            ``AsyncGenerator[ChatResponse]`` for streaming calls.

        Raises:
            ValueError: If ``messages`` is not a list or if any message
                is missing ``role`` / ``content`` keys.
        """
        if not isinstance(messages, list):
            raise ValueError(f"messages must be list, got {type(messages)}")
        if not all("role" in m and "content" in m for m in messages):
            raise ValueError("Each message must have 'role' and 'content' keys")

        api_kwargs: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": self.stream,
            **self.generate_kwargs,
            **kwargs,
        }

        if tools:
            api_kwargs["tools"] = tools

        if tool_choice:
            if tool_choice in {"auto", "none", "required"}:
                api_kwargs["tool_choice"] = tool_choice
            else:
                api_kwargs["tool_choice"] = {
                    "type": "function",
                    "function": {"name": tool_choice},
                }

        if self.stream:
            api_kwargs["stream_options"] = {"include_usage": True}

        start_datetime = datetime.now()
        response = await self.client.chat.completions.create(**api_kwargs)

        if self.stream:
            return self._parse_stream_response(start_datetime, response)

        return self._parse_completion_response(start_datetime, response)

    # ------------------------------------------------------------------
    #  Private: Parse stream response
    # ------------------------------------------------------------------

    async def _parse_stream_response(
        self,
        start_datetime: datetime,
        response: AsyncStream,
    ) -> AsyncGenerator[ChatResponse]:
        """Parse a streaming chat completion into ``ChatResponse`` chunks.

        Handles incremental text, thinking/reasoning content, and
        partial tool-call argument accumulation.  Yields a
        ``ChatResponse`` for each chunk received.

        Args:
            start_datetime: The timestamp when the API call began
                (used for usage timing).
            response: The raw ``AsyncStream`` from the OpenAI client.

        Yields:
            ``ChatResponse`` objects with the accumulated content so far.
        """
        usage = None
        response_id: str | None = None
        text = ""
        thinking = ""
        tool_calls: dict[int, dict] = {}
        contents: list = []
        _chunk_count = 0

        async with response as stream:
            async for item in stream:
                chunk = item
                _chunk_count += 1
                if _chunk_count <= 3:
                    logger.info(
                        "STREAM chunk #%d: id=%r choices=%d has_usage=%s",
                        _chunk_count,
                        getattr(chunk, "id", None),
                        len(chunk.choices),
                        chunk.usage is not None,
                    )
                if response_id is None:
                    response_id = getattr(chunk, "id", None)
                if chunk.usage:
                    usage = ChatUsage(
                        input_tokens=chunk.usage.prompt_tokens,
                        output_tokens=chunk.usage.completion_tokens,
                        time=(datetime.now() - start_datetime).total_seconds(),
                    )
                if not chunk.choices:
                    if usage and contents:
                        yield ChatResponse(content=contents, usage=usage, id=response_id or "")
                    continue

                choice = chunk.choices[0]
                delta_reasoning = (
                    getattr(choice.delta, "reasoning", None)
                    or getattr(choice.delta, "reasoning_content", None)
                    or ""
                )
                delta_content = getattr(choice.delta, "content", None)
                if _chunk_count <= 3:
                    logger.info(
                        "STREAM chunk #%d delta: content=%r reasoning_content=%r "
                        "reasoning=%r tool_calls=%r",
                        _chunk_count,
                        delta_content,
                        getattr(choice.delta, "reasoning_content", None),
                        getattr(choice.delta, "reasoning", None),
                        getattr(choice.delta, "tool_calls", None),
                    )

                thinking += delta_reasoning
                text += delta_content or ""

                for tc in getattr(choice.delta, "tool_calls", None) or []:
                    func = getattr(tc, "function", None)
                    if func is None:
                        continue
                    if tc.index in tool_calls:
                        if func.arguments is not None:
                            tool_calls[tc.index]["input"] += func.arguments
                    else:
                        tool_calls[tc.index] = {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": func.name,
                            "input": func.arguments or "",
                        }

                contents = []
                if thinking:
                    contents.append({"type": "thinking", "thinking": thinking})
                if text:
                    contents.append({"type": "response", "response": text})

                for tc in tool_calls.values():
                    contents.append(
                        {
                            "type": tc["type"],
                            "id": tc["id"],
                            "name": tc["name"],
                            "input": tc["input"],
                        }
                    )

                if contents:
                    yield ChatResponse(content=contents, usage=usage, id=response_id or "")

    # ------------------------------------------------------------------
    #  Private: Parse completion response
    # ------------------------------------------------------------------

    def _parse_completion_response(
        self,
        start_datetime: datetime,
        response: ChatCompletion,
    ) -> ChatResponse:
        """Parse a non-streaming chat completion into a ``ChatResponse``.

        Args:
            start_datetime: The timestamp when the API call began.
            response: The ``ChatCompletion`` object from the OpenAI
                client.

        Returns:
            A single ``ChatResponse`` with all content blocks and usage.
        """
        content_blocks: list = []

        if response.choices:
            choice = response.choices[0]
            reasoning = (
                getattr(choice.message, "reasoning", None)
                or getattr(choice.message, "reasoning_content", None)
                or ""
            )
            if reasoning:
                content_blocks.append({"type": "thinking", "thinking": reasoning})

            if choice.message.content:
                content_blocks.append({"type": "response", "response": choice.message.content})

            for tc in choice.message.tool_calls or []:
                func = getattr(tc, "function", None)
                if func is None:
                    continue
                content_blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": func.name,
                        "input": _json_loads_with_repair(func.arguments),
                    }
                )

        usage = None
        if response.usage:
            usage = ChatUsage(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                time=(datetime.now() - start_datetime).total_seconds(),
            )

        return ChatResponse(
            content=content_blocks,
            usage=usage,
            id=getattr(response, "id", ""),
        )
