"""Pure chat render pipeline — plan building and streaming body rendering.

This module contains no Qt model or QML access: it turns a message list into
role-keyed chat items (a render plan) and turns streamed text into in-place row
updates.  It is executed on a per-chat worker thread, so it must stay free of
GUI-thread-only state; the shared Markdown parser is thread-local and the card
builders return plain dicts.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any

from ..util.tokens.counter import count_tokens
from .chat_items import (
    _parse_tool_arguments,
    build_response_item,
    build_response_pending_item,
    build_thinking_item,
    build_thinking_pending_item,
    build_tool_call_item,
    build_tool_call_pending_item,
    build_tool_result_item,
    build_tool_result_pending_item,
    build_user_item,
    build_waiting_item,
    thinking_body_parts,
)
from .context_banner import build_context_banner_item, build_context_sections_from_snapshot
from .markdown import IncrementalMarkdown
from .qt_roles import ChatRole

#: Messages older than this many from the end are built with their card bodies
#: collapsed, so their rich text is never laid out.  Collapsed keys carry a
#: ``:c`` suffix so ageing a message out rebuilds it once.
_COLLAPSE_OLDER_THAN = 12

#: Minimum seconds between in-place streaming body updates for one chat.
_STREAM_UPDATE_INTERVAL = 0.08


# ------------------------------------------------------------------
#  Module-level content helpers
# ------------------------------------------------------------------


def content_hash(data: str | list) -> str:
    """Return a short stable content hash for render planning.

    Args:
        data: A string or a JSON-serializable list.

    Returns:
        A 16-character blake2b hex digest.
    """
    if isinstance(data, list):
        data = json.dumps(data, sort_keys=True)
    return hashlib.blake2b(data.encode()).hexdigest()[:16]


def extract_text_from_multimodal(content_parts: list) -> str:
    """Extract text parts from a multimodal content list for display.

    Args:
        content_parts: Content part dicts (``{"type": "text", ...}`` or
            ``{"type": "image_url", ...}``).

    Returns:
        Joined text parts, or ``"[IMAGE]"`` if there are no text parts.
    """
    texts: list[str] = []
    for part in content_parts:
        if isinstance(part, dict) and part.get("type") == "text":
            texts.append(part.get("text", ""))
    return "\n".join(texts) if texts else "[IMAGE]"


def normalize_content(content: str | list) -> str:
    """Normalise message content to a string for hashing and display.

    Args:
        content: Either a string or a multimodal content list.

    Returns:
        String representation of the content.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return extract_text_from_multimodal(content)
    return str(content)


def assistant_decision(msg: dict) -> dict[str, Any]:
    """Extract common decision state from an assistant message.

    Args:
        msg: The assistant message dict.

    Returns:
        Dict with thinking/response text, tool-call lists, done flags, and
        ``finalized_ids``.
    """
    thinking_text = msg.get("reasoning_content", "")
    content_text = msg.get("content", "") or ""
    tool_calls = msg.get("tool_calls", [])
    streaming_tcs = msg.get("_streaming_tool_calls", [])
    return {
        "thinking_text": thinking_text,
        "content_text": content_text,
        "tool_calls": tool_calls,
        "streaming_tcs": streaming_tcs,
        "effective_tool_calls": streaming_tcs or tool_calls,
        "thinking_done": bool(content_text) or bool(tool_calls),
        "response_done": bool(tool_calls),
        "finalized_ids": {tc.get("id", "") for tc in tool_calls},
    }


def is_waiting_for_assistant(messages: list[dict], is_busy: bool) -> bool:
    """Return whether the UI should show the pre-response waiting scanner.

    Args:
        messages: The chat's message list.
        is_busy: Whether a generation is running.

    Returns:
        ``True`` while busy but the current assistant turn has not yet produced
        thinking, response, or tool-call content.
    """
    if not is_busy or not messages:
        return False
    last = messages[-1]
    if last.get("role") != "assistant":
        return True
    decision = assistant_decision(last)
    return not (
        decision["thinking_text"] or decision["content_text"] or decision["effective_tool_calls"]
    )


def count_trailing_tool_results(messages: list[dict], after_idx: int) -> int:
    """Count consecutive tool-result messages after *after_idx*.

    Args:
        messages: The full message list.
        after_idx: The index to start counting after.

    Returns:
        The number of leading ``role == "tool"`` messages.
    """
    count = 0
    for j in range(after_idx + 1, len(messages)):
        if messages[j].get("role") == "tool":
            count += 1
        else:
            break
    return count


def delete_bounds(messages: list[dict], msg_index: int) -> tuple[int, int]:
    """Return the ``[start, end)`` range to remove for one card delete.

    Each card maps to one message object; only the minimum extra messages
    required to keep the OpenAI sequence valid go with it.

    Args:
        messages: The full message list.
        msg_index: Index of the message the clicked card was built from.

    Returns:
        The half-open ``(start, end)`` range to remove.
    """
    start = msg_index
    end = msg_index + 1
    role = messages[msg_index].get("role", "")
    if role == "assistant":
        end += count_trailing_tool_results(messages, msg_index)
    elif role == "tool":
        prev = start - 1
        if prev >= 0 and messages[prev].get("role") == "assistant":
            remaining = count_trailing_tool_results(messages, prev)
            if messages[prev].get("tool_calls") and remaining <= 1:
                start = prev
    return start, end


def accumulate_tokens(text: str, previous: str, current: int) -> int:
    """Accumulate a token estimate for streamed text.

    Args:
        text: The full current text.
        previous: The previously counted prefix.
        current: The previous accumulated token count.

    Returns:
        The updated token count.
    """
    old_len = len(previous)
    if old_len <= len(text):
        return current + count_tokens(text[old_len:])
    return count_tokens(text)


# ------------------------------------------------------------------
#  Render state
# ------------------------------------------------------------------


@dataclass
class CardRender:
    """Worker-side tracking state for one streaming card (thinking/response).

    Attributes:
        item_index: Row index of the card in the plan produced for the model.
        token_count: Last rendered token count for the card.
        markdown: Incremental renderer that reuses the committed HTML across
            stream ticks (response only).
        last_prefix_html: The frozen-prefix HTML last pushed to the model.
    """

    item_index: int | None = None
    token_count: int = 0
    markdown: IncrementalMarkdown = field(default_factory=IncrementalMarkdown)
    last_prefix_html: str = ""

    def reset(self) -> None:
        """Clear the card tracking state."""
        self.item_index = None
        self.token_count = 0
        self.markdown.reset()
        self.last_prefix_html = ""


@dataclass
class RenderState:
    """Worker-side render/tracking state for one chat.

    Attributes:
        item_cache: Rendered chat items keyed by their identity key.
        thinking: Streaming state for the thinking card.
        response: Streaming state for the response card.
        tool_call_indices: Row indices of the streaming tool-call cards.
        last_rendered_thinking_text: Last thinking text pushed to the model.
        last_rendered_message_text: Last response text pushed to the model.
        last_rendered_tool_calls: Last rendered tool-call count.
        last_rendered_tool_results: Last rendered tool-result count.
        last_rendered_streaming_tc_json: Last rendered streaming tool-call JSON.
        last_tok_counted_thinking: Thinking prefix already counted for tokens.
        last_tok_counted_response: Response prefix already counted for tokens.
        last_content_update_time: Monotonic time of the last content-only update.
        last_rebuild_time: Monotonic time of the last structural rebuild.
    """

    item_cache: dict[str, dict[int, object]] = field(default_factory=dict)
    thinking: CardRender = field(default_factory=CardRender)
    response: CardRender = field(default_factory=CardRender)
    tool_call_indices: list[int] = field(default_factory=list)
    last_rendered_thinking_text: str = ""
    last_rendered_message_text: str = ""
    last_rendered_tool_calls: int = 0
    last_rendered_tool_results: int = 0
    last_rendered_streaming_tc_json: str = ""
    last_tok_counted_thinking: str = ""
    last_tok_counted_response: str = ""
    last_content_update_time: float = 0.0
    last_rebuild_time: float = 0.0

    def reset_turn(self) -> None:
        """Reset per-turn streaming and render-tracking state."""
        self.thinking.reset()
        self.response.reset()
        self.tool_call_indices.clear()
        self.last_rendered_thinking_text = ""
        self.last_rendered_message_text = ""
        self.last_rendered_tool_calls = 0
        self.last_rendered_tool_results = 0
        self.last_rendered_streaming_tc_json = ""
        self.last_tok_counted_thinking = ""
        self.last_tok_counted_response = ""
        self.last_content_update_time = 0.0
        self.last_rebuild_time = 0.0


@dataclass
class RenderIndices:
    """Row locations of the streaming-capable cards produced by a plan.

    Attributes:
        thinking_index: Row index of the pending thinking card, or ``None``.
        response_index: Row index of the pending response card, or ``None``.
        tool_call_indices: Row indices of the streaming tool-call cards.
    """

    thinking_index: int | None = None
    response_index: int | None = None
    tool_call_indices: list[int] = field(default_factory=list)


@dataclass
class RenderPlan:
    """A full render plan for one chat.

    Attributes:
        keys: Per-row identity keys, parallel to ``items``.
        items: Role-keyed chat rows consumed by ``ChatListModel.diff_update``.
        snapshot: The context snapshot used, if any.
        indices: Streaming-card row indices extracted while building.
    """

    keys: list[str]
    items: list[dict[int, object]]
    snapshot: dict[str, Any] | None
    indices: RenderIndices


# ------------------------------------------------------------------
#  Plan builder
# ------------------------------------------------------------------


class PlanBuilder:
    """Accumulate render-plan keys and items, reusing cached items by key.

    Attributes:
        state: The chat's render state, which owns the item cache.
        keys: Accumulated identity keys, parallel to ``items``.
        items: Accumulated role-keyed items.
        indices: Streaming-card row indices recorded while building.
    """

    def __init__(self, state: RenderState) -> None:
        """Initialise the builder.

        Args:
            state: The chat's render state.
        """
        self.state = state
        self.keys: list[str] = []
        self.items: list[dict[int, object]] = []
        self.indices = RenderIndices()

    def emit(
        self,
        key: str,
        builder: Callable[[], dict[int, object]],
        *,
        cacheable: bool = True,
    ) -> int:
        """Append one item, reusing the cache for finalized ``key``s.

        Args:
            key: The row's identity key.
            builder: Callable producing the item on a cache miss.
            cacheable: Whether the item may be cached.

        Returns:
            The appended row index.
        """
        item = self.state.item_cache.get(key) if cacheable else None
        if item is None:
            item = builder()
            if cacheable:
                self.state.item_cache[key] = item
        self.keys.append(key)
        self.items.append(item)
        return len(self.items) - 1


# ------------------------------------------------------------------
#  Renderer
# ------------------------------------------------------------------


class ChatRenderer:
    """Pure render pipeline for one chat (worker-thread only).

    Attributes:
        state: The chat's render state.
    """

    def __init__(self, state: RenderState | None = None) -> None:
        """Initialise the renderer.

        Args:
            state: Optional pre-built render state.
        """
        self.state = state or RenderState()

    # ------------------------------------------------------------------
    #  Public: cache / indices
    # ------------------------------------------------------------------

    def invalidate_cache(self) -> None:
        """Drop every cached rendered item."""
        self.state.item_cache.clear()

    def reset_turn(self) -> None:
        """Reset per-turn render state."""
        self.state.reset_turn()

    # ------------------------------------------------------------------
    #  Public: plan building
    # ------------------------------------------------------------------

    def build_plan(
        self,
        messages: list[dict],
        snapshot: dict | None,
        banners: list[dict],
        is_busy: bool,
    ) -> RenderPlan:
        """Build a full render plan for a chat.

        Args:
            messages: The chat message list.
            snapshot: The cached context snapshot, if any.
            banners: Skill-update banners, each anchored to a message index.
            is_busy: Whether the chat is currently generating.

        Returns:
            The populated :class:`RenderPlan`.
        """
        builder = PlanBuilder(self.state)
        if snapshot:
            builder.emit(
                "b:i",
                lambda: build_context_banner_item(
                    "Original System Context",
                    build_context_sections_from_snapshot(snapshot),
                    is_delta=False,
                ),
            )
        message_count = len(messages)
        banners_by_anchor: dict[int, list[dict]] = {}
        for banner in banners:
            anchor = int(banner.get("anchor", 0) or 0)
            anchor = max(0, min(anchor, message_count))
            banners_by_anchor.setdefault(anchor, []).append(banner)

        emitted_anchors: set[int] = set()

        def emit_banners(anchor: int) -> None:
            if anchor in emitted_anchors:
                return
            emitted_anchors.add(anchor)
            for banner in banners_by_anchor.get(anchor, []):
                content = {
                    "title": banner.get("title", "Skill Update"),
                    "sections": banner.get("sections", []),
                    "is_delta": banner.get("is_delta", True),
                }
                key = f"b:d:{anchor}:" + content_hash(json.dumps(content, sort_keys=True))
                builder.emit(
                    key,
                    lambda banner=banner: build_context_banner_item(
                        banner.get("title", "Skill Update"),
                        banner.get("sections", []),
                        is_delta=banner.get("is_delta", True),
                    ),
                )

        emit_banners(0)
        recent_start = max(0, len(messages) - _COLLAPSE_OLDER_THAN)
        for i, msg in enumerate(messages):
            emit_banners(i)
            role = msg.get("role", "")
            is_last_busy = is_busy and i == len(messages) - 1 and role == "assistant"
            collapsed = i < recent_start
            suffix = ":c" if collapsed else ""
            if role == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = extract_text_from_multimodal(content)
                builder.emit(
                    f"u:{i}:" + content_hash(msg.get("content", "")) + suffix,
                    lambda content=content, collapsed=collapsed, i=i: build_user_item(
                        content, collapsed=collapsed, msg_index=i
                    ),
                )
            elif role == "assistant":
                self._build_assistant_plan(builder, msg, messages, i, is_last_busy, collapsed)
            elif role == "tool":
                content = msg.get("content", "")
                name = msg.get("name", "")
                builder.emit(
                    f"tr:{i}:" + name + ":" + content_hash(content) + suffix,
                    lambda name=name, content=content, collapsed=collapsed, i=i: (
                        build_tool_result_item(
                            name,
                            content,
                            token_count=count_tokens(content),
                            collapsed=collapsed,
                            msg_index=i,
                        )
                    ),
                )
        emit_banners(message_count)
        if is_waiting_for_assistant(messages, is_busy):
            builder.emit("w:pending", build_waiting_item, cacheable=False)
        return RenderPlan(builder.keys, builder.items, snapshot, builder.indices)

    def _build_assistant_plan(
        self,
        builder: PlanBuilder,
        msg: dict,
        messages: list[dict],
        idx: int,
        is_last_busy: bool,
        collapsed: bool,
    ) -> None:
        """Append the plan entries for one assistant message."""
        d = assistant_decision(msg)
        if is_last_busy:
            self._build_streaming_assistant_plan(builder, d, messages, idx)
            return
        suffix = ":c" if collapsed else ""
        if d["thinking_text"]:
            text = d["thinking_text"]
            builder.emit(
                f"t:{idx}:" + content_hash(text) + suffix,
                lambda text=text, collapsed=collapsed, idx=idx: build_thinking_item(
                    text, token_count=count_tokens(text), collapsed=collapsed, msg_index=idx
                ),
            )
        if d["content_text"]:
            text = d["content_text"]
            builder.emit(
                f"r:{idx}:" + content_hash(text) + suffix,
                lambda text=text, collapsed=collapsed, idx=idx: build_response_item(
                    text, token_count=count_tokens(text), collapsed=collapsed, msg_index=idx
                ),
            )
        for tc in d["effective_tool_calls"]:
            name = tc.get("function", {}).get("name", "")
            args_str = tc.get("function", {}).get("arguments", "{}")
            tc_id = tc.get("id", "")
            builder.emit(
                f"c:{idx}:" + name + ":" + content_hash(args_str) + ":" + tc_id + suffix,
                lambda tc=tc, collapsed=collapsed, idx=idx: build_tool_call_item(
                    {
                        "name": tc.get("function", {}).get("name", ""),
                        "arguments": _parse_tool_arguments(tc),
                        "mode": tc.get("_mode", "ask"),
                    },
                    token_count=count_tokens(tc.get("function", {}).get("arguments", "{}")),
                    collapsed=collapsed,
                    msg_index=idx,
                ),
            )

    def _build_streaming_assistant_plan(
        self,
        builder: PlanBuilder,
        d: dict[str, Any],
        messages: list[dict],
        idx: int,
    ) -> None:
        """Append streaming plan entries (with pending cards) for the busy assistant."""
        state = builder.state
        if d["thinking_text"]:
            text = d["thinking_text"]
            if d["thinking_done"]:
                builder.emit(
                    f"t:{idx}:" + content_hash(text) + ":done",
                    lambda text=text, idx=idx: build_thinking_item(
                        text, token_count=count_tokens(text), msg_index=idx
                    ),
                    cacheable=False,
                )
            else:
                row = builder.emit(
                    f"t:{idx}:pending",
                    lambda text=text, idx=idx: build_thinking_pending_item(
                        text, token_count=state.thinking.token_count, msg_index=idx
                    ),
                    cacheable=False,
                )
                builder.indices.thinking_index = row
        if d["content_text"]:
            text = d["content_text"]
            if d["response_done"]:
                builder.emit(
                    f"r:{idx}:" + content_hash(text) + ":done",
                    lambda text=text, idx=idx: build_response_item(
                        text, token_count=count_tokens(text), msg_index=idx
                    ),
                    cacheable=False,
                )
            else:
                row = builder.emit(
                    f"r:{idx}:pending",
                    lambda text=text, idx=idx: build_response_pending_item(
                        text, token_count=state.response.token_count, msg_index=idx
                    ),
                    cacheable=False,
                )
                builder.indices.response_index = row
        for tc in d["effective_tool_calls"]:
            tc_id = tc.get("id", "")
            name = tc.get("function", {}).get("name", "")
            mode = tc.get("_mode", "ask")
            args_str = tc.get("function", {}).get("arguments", "{}")
            if tc_id in d["finalized_ids"]:
                row = builder.emit(
                    f"c:{idx}:" + name + ":" + content_hash(args_str) + ":f",
                    lambda tc=tc, idx=idx: build_tool_call_item(
                        {
                            "name": tc.get("function", {}).get("name", ""),
                            "arguments": _parse_tool_arguments(tc),
                            "mode": tc.get("_mode", "ask"),
                        },
                        token_count=count_tokens(tc.get("function", {}).get("arguments", "{}")),
                        msg_index=idx,
                    ),
                    cacheable=False,
                )
            else:
                row = builder.emit(
                    f"c:{idx}:p:" + name + ":" + tc_id,
                    lambda name=name, mode=mode, args_str=args_str, idx=idx: (
                        build_tool_call_pending_item(
                            name, mode, count_tokens(args_str), msg_index=idx
                        )
                    ),
                    cacheable=False,
                )
            builder.indices.tool_call_indices.append(row)
        if d["tool_calls"]:
            result_count = count_trailing_tool_results(messages, idx)
            for k in range(result_count, len(d["tool_calls"])):
                tc = d["tool_calls"][k]
                name = tc.get("function", {}).get("name", "")
                tc_id = tc.get("id", "")
                builder.emit(
                    "ptr:" + name + ":" + tc_id,
                    lambda name=name, tc_id=tc_id: build_tool_result_pending_item(name, tc_id),
                    cacheable=False,
                )
        self._apply_indices(builder.indices)

    def _apply_indices(self, indices: RenderIndices) -> None:
        """Record a plan's streaming-card indices on the render state."""
        self.state.thinking.item_index = indices.thinking_index
        self.state.response.item_index = indices.response_index
        self.state.tool_call_indices = list(indices.tool_call_indices)
        self.state.thinking.last_prefix_html = ""
        self.state.response.last_prefix_html = ""

    # ------------------------------------------------------------------
    #  Public: stream detection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def stream_decision(msg: dict) -> dict[str, Any]:
        """Return the diff-relevant fields of an assistant message."""
        return assistant_decision(msg)

    # ------------------------------------------------------------------
    #  Public: streaming body updates
    # ------------------------------------------------------------------

    def build_stream_update(
        self,
        thinking_text: str,
        content_text: str,
        streaming_tcs: list | None,
        thinking_changed: bool,
        content_changed: bool,
    ) -> list[tuple[int, dict[int, object]]]:
        """Compute in-place row updates for a streaming tick.

        Args:
            thinking_text: Current thinking text.
            content_text: Current response text.
            streaming_tcs: Live streaming tool calls, if any.
            thinking_changed: Whether the thinking text changed.
            content_changed: Whether the response text changed.

        Returns:
            A list of ``(row, role_values)`` updates to merge into the model.
        """
        card = self.state
        updates: list[tuple[int, dict[int, object]]] = []
        if thinking_changed:
            card.thinking.token_count = accumulate_tokens(
                thinking_text, card.last_tok_counted_thinking, card.thinking.token_count
            )
            card.last_tok_counted_thinking = thinking_text
            if card.thinking.item_index is not None:
                updates.append(
                    self._streaming_body_update(
                        card.thinking.item_index,
                        thinking_body_parts(thinking_text),
                        card.thinking,
                    )
                )
        if content_changed:
            card.response.token_count = accumulate_tokens(
                content_text, card.last_tok_counted_response, card.response.token_count
            )
            card.last_tok_counted_response = content_text
            if card.response.item_index is not None:
                updates.append(
                    self._streaming_body_update(
                        card.response.item_index,
                        card.response.markdown.render_parts(content_text),
                        card.response,
                    )
                )
        if streaming_tcs:
            for idx, tc in enumerate(streaming_tcs):
                if idx >= len(card.tool_call_indices):
                    break
                args_str = tc.get("function", {}).get("arguments", "{}")
                updates.append(
                    (
                        card.tool_call_indices[idx],
                        {int(ChatRole.TOKEN_TEXT): f"{count_tokens(args_str)} tk"},
                    )
                )
        return updates

    def _streaming_body_update(
        self,
        row: int,
        parts: tuple[str, str],
        card: CardRender,
    ) -> tuple[int, dict[int, object]]:
        """Build the role values for one streaming card body update."""
        prefix_html, tail_html = parts
        values: dict[int, object] = {
            int(ChatRole.BODY_TAIL_HTML): tail_html,
            int(ChatRole.TOKEN_TEXT): f"{card.token_count} tk",
        }
        if prefix_html != card.last_prefix_html:
            card.last_prefix_html = prefix_html
            values[int(ChatRole.BODY_HTML)] = prefix_html
        return row, values

    def build_result_replacement(
        self, tool_name: str, content: str, msg_index: int
    ) -> tuple[dict[int, object], str]:
        """Build the real tool-result item and key for an in-place swap.

        Args:
            tool_name: Tool name for the result card.
            content: Result content text.
            msg_index: Index of the source tool message.

        Returns:
            A ``(item, key)`` pair.
        """
        item = build_tool_result_item(
            tool_name, content, token_count=count_tokens(content), msg_index=msg_index
        )
        key = f"tr:{msg_index}:{tool_name}:{content_hash(content)}"
        return item, key


# ------------------------------------------------------------------
#  Context snapshot
# ------------------------------------------------------------------


def build_context_snapshot(agent: Any) -> dict[str, Any]:
    """Build a context snapshot dict from a live agent.

    Args:
        agent: The live agent object.

    Returns:
        A dict with system_prompt, pending_additions, and skill/tool config.
    """
    return {
        "system_prompt": agent.sys_prompt,
        "pending_additions": agent._pending_sys_message,
        "activated_skills": agent.activated_skills,
        "tools": agent._tools,
        "tool_config": agent._tool_config,
    }
