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
   │  format_tool_change); return early while _loading_chat_config
   ▼
_schedule_sync → _spawn(_sync_config_to_chat)
   │
   ▼
_collect_sidebar_config
   │  _collect_selected_skills + _collect_tool_modes + build_tool_config
   │  -> {primary, secondary, tools}
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
chat_manager.update_chat_config(sid, ...)
   │  -> Agent.update_skill_config
   │     - compute removed/demoted -> warnings
   │     - accumulate new instructions -> _pending_sys_message
   │     - register new tools, set tool_config
   │     - return {warnings, added_primary, added_secondary, added_tools}
   ▼
if warnings: toast each
   │
   ▼
_append_delta_banner (pops the previous delta, appends the new one)
   │
   ▼
chat.rebuild_chat_display(chat_id)
```

## Key detail: `_pending_sys_message`

`Agent.update_skill_config` does **not** mutate the system prompt. Instead it
accumulates new primary instructions + secondary descriptions into
`_pending_sys_message`. On the next `run()`, the agent flushes this buffer as a
`system` message **before** the user message, so the LLM receives the new
context mid-conversation. Removal/demotion only produces warnings, because
content already in the conversation history cannot be withdrawn.

## Delta banner

`build_delta_context_sections` produces sections:

- **Added Primary Skills** (name + truncated instructions)
- **Added Secondary Skills** (name + description)
- **Added Tools** (name + description)
- **Tool Mode Changes** (`old → new`)

The banner appears in the chat as a distinct orange "Context Update" block.
Only one delta banner is kept: `_append_delta_banner` pops the previous delta
before appending the new one. The banner is a derived UI item — it is stored on
`ChatState.context_banners_data`, not in `chat.messages`.

## When no live chat exists

If the active chat has not been hydrated there is no live `Agent`, so
`_apply_live_config` returns after `_persist_config`, `_publish_config_summary`,
and `_update_config_chips`: the selections are saved and the panel counts
refresh, but no push or delta banner happens. The persisted config takes effect
the next time the chat is hydrated.
