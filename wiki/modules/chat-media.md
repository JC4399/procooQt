# chat.media — disk-backed multimodal media

Source: `src/chat/media.py`

## Purpose

Images and other multimodal payloads arrive from tools and sub-agents as base64
`data:` URLs. Keeping those strings in `Agent.messages` makes the conversation
history large and forces every persistence write to re-serialize them. This
module writes the decoded bytes once under `storage/media/<chat_id>/` and stores a
compact `procoo-media://` reference in the message instead. The reference is
expanded back to a data URL only when a prompt is sent to the LLM.

Related: [`chat-agent`](chat-agent.md), [`chat-store`](chat-store.md).

## Deliverables

- `MediaStore.store_data_url(chat_id, url)` — persist a base64 data URL and return
  a `procoo-media://<chat>/<file>` reference.
- `MediaStore.resolve(url)` — expand a reference back to a data URL, with a small
  in-memory LRU memo (`memo_limit = 8`).
- `MediaStore.expand_message(value)` — recursively replace media references in a
  copied message tree before an LLM call.
- `safe_media_name(value)` — filesystem-safe folder name shared with
  `ChatStore` for media cleanup.

## Steps / Flow

### Store

1. Match `data:<mime>;base64,<payload>`.
2. Decode the payload and hash it with blake2b.
3. Write `storage/media/<safe_chat_id>/<hash>.<ext>` if it does not already exist.
4. Return `procoo-media://<safe_chat_id>/<hash>.<ext>`.

### Resolve

1. Return non-`procoo-media://` URLs unchanged.
2. Check the LRU memo.
3. Resolve the path inside `media_dir` (rejecting traversal), read the bytes, and
   rebuild the data URL from the file extension's MIME type.
4. Cache the result and evict the oldest entry above `memo_limit`.

### Prompt expansion

`Agent._build_prompt` first deep-copies each message with
`_strip_internal_keys`, then calls `expand_message` on the copy. The copy is
mutated in place, so no second copy of the message list is made.

## Function Reference

| Signature | Inputs | Output | Flow | Side effects |
|---|---|---|---|---|
| `def safe_media_name(value: str) -> str` | chat id | safe folder name | replace non `[A-Za-z0-9_.-]` characters | — |
| `def __init__(self, media_dir: str, *, memo_limit: int = 8)` | media root, memo size | `None` | create `media_dir` | creates directory |
| `def store_data_url(self, chat_id, url) -> str` | chat id, data URL | media reference or original URL | decode → hash → write file | writes media file |
| `def resolve(self, url) -> str` | reference or URL | data URL or original URL | memo → path check → read → encode | reads media file; updates memo |
| `def expand_message(self, value) -> Any` | copied message tree | same tree | recursively replace `image_url` refs | mutates the copied tree |
| `def _resolve_path(self, url) -> Path \| None` | reference | path inside `media_dir` or `None` | resolve + containment check | — |
