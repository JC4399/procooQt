# Config sync flow

How a skill-dock change (checkbox / radio / preset) propagates to the active
chat and renders a context delta banner.

Related: [`qt-skill-controller`](../modules/qt-skill-controller.md), [`chat-agent`](../modules/chat-agent.md), [`qt-context-banner`](../modules/qt-context-banner.md).

## Sequence

```
sidebar checkbox / radio / preset change (SkillDock.qml)
   │
   ▼
skill._handle_skill_toggle / _handle_tool_mode_change / _handle_load_preset
   │  update models + selected counts + log (format_skill_change /
   │  format_tool_change); preset paths are normalized to forward slashes;
   │  return early while _loading_chat_config
   ▼
_schedule_sync → _spawn(_sync_config_to_chat)
   │
   ▼
_collect_sidebar_config
   │  _collect_selected_skills + _collect_tool_modes + build_tool_config
   │  -> {activated, tools}
   ▼
_persist_config: stored["skills_config"] = config; save_chat
   │  returns the previous tool-mode mapping
   ▼
_publish_config_summary (per-chat counts → panel) + _update_config_chips (legacy)
   │
   ▼
_apply_live_config (only when a live chat exists)
   │  await asyncio.to_thread(_load_config_payloads)
   │     load_skill_contents + load_tool_functions + build_tool_config
   ▼
worker.update_config(...)   [call_soon_threadsafe to the chat's thread]
   │  -> Agent.update_skill_config
   │     - no user message yet: _replace_skill_config
   │         rebuild sys_prompt + tool set exactly (add/remove freely)
   │     - chat started: _apply_skill_delta
   │         compute removed/demoted -> warnings
   │         accumulate new instructions -> _pending_sys_message
   │         register new tools, set tool_config
   │     - return {warnings, added_activated, added_tools}
   ▼ (worker emits config_updated → chat.config_updated)
if warnings: toast each
   │
   ▼
worker.append_banner(...) (pops the previous delta, appends the new one)
   │
   ▼
worker.request_rebuild()
```

## Key detail: pre-start replacement vs. post-start delta

Before the first user message, `Agent.update_skill_config` calls
`_replace_skill_config`: it rebuilds `sys_prompt` from the base system message
and the new skill contents, refreshes the token tracker, replaces `_tools`
exactly, clears `_pending_sys_message`, and resets the committed sets. Skills
can therefore be added **and removed** freely, and no delta banner is produced.

Once a `role: user` message exists, `update_skill_config` calls
`_apply_skill_delta`. It does **not** mutate the system prompt; instead it
accumulates new activated instructions into `_pending_sys_message`. On the next `run()`, the agent flushes this buffer as a
`system` message **before** the user message, so the LLM receives the new
context mid-conversation. Removal/demotion only produces warnings, because
content already in the conversation history cannot be withdrawn.

## Delta banner

`build_delta_context_sections` produces sections:

- **Added Activated Skills** (name + truncated instructions)
- **Added Tools** (name + description)
- **Tool Mode Changes** (`old → new`)

The banner appears in the chat as a distinct orange "Context Update" block.
Only one delta banner is kept: `worker.append_banner` pops the previous delta
before appending the new one. The banner is a derived UI item — it is held on the
chat [`ChatWorker`](../modules/chat-worker.md), not in `chat.messages`.

## When no live chat exists

If the active chat has not been hydrated there is no live `Agent`, so
`_apply_live_config` returns after `_persist_config`, `_publish_config_summary`,
and `_update_config_chips`: the selections are saved and the panel counts
refresh, but no push or delta banner happens. The persisted config takes effect
the next time the chat is hydrated.
