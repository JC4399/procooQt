# Config sync flow

How a skill-dock change (checkbox / radio / preset) propagates to the active
chat and renders a skill-update context banner.

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
_schedule_sync → _spawn(_sync_config_to_chat(generation))
   │
   ▼
_collect_sidebar_config
   │  _collect_selected_skills + _collect_tool_modes + build_tool_config
   │  -> {activated, tools}
   ▼
_persist_config: stored["skills_config"] = config; save_chat
   │
   ▼
_publish_config_summary (per-chat counts → panel) + _update_config_chips (legacy)
   │
   ▼
_apply_live_config (only when a live chat exists)
   │  await asyncio.to_thread(_load_config_payloads)
   │     load_skill_contents + load_tool_functions + build_tool_config
   │  skip if a newer sync generation has started
   ▼
worker.update_config(...)   [call_soon_threadsafe to the chat's thread]
   │  -> Agent.update_skill_config
   │     - no user message yet: _replace_skill_config
   │         rebuild sys_prompt + tool set exactly (add/remove freely)
   │     - chat started: _apply_skill_delta
   │         compute removed/demoted -> warnings
   │         accumulate new instructions -> _pending_sys_message
   │         register new tools, set tool_config
   │     - return {warnings, added_activated, added_tools, pending_sys_message}
   ▼
worker._sync_pending_banner(result)
   │  text = result["pending_sys_message"].strip()
   │  remove the existing pending banner
   │  if text: append a pending "Skill Update" banner anchored at
   │           len(agent.messages), body = exact text (fenced System Prompt)
   │  rebuild if visible
   ▼ (worker emits config_updated → chat.config_updated)
if warnings: toast each
```

## Key detail: pre-start replacement vs. post-start delta

Before the first user message, `Agent.update_skill_config` calls
`_replace_skill_config`: it rebuilds `sys_prompt` from the base system message
and the new skill contents, refreshes the token tracker, replaces `_tools`
exactly, clears `_pending_sys_message`, and resets the committed sets. Skills
can therefore be added **and removed** freely, and no skill-update banner is
produced.

Once a `role: user` message exists, `update_skill_config` calls
`_apply_skill_delta`. It does **not** mutate the system prompt; instead it
accumulates new activated instructions into `_pending_sys_message`. On the next `run()`, the agent flushes this buffer as a
`system` message **before** the user message, so the LLM receives the new
context mid-conversation. Removal/demotion only produces warnings, because
content already in the conversation history cannot be withdrawn.

## Skill-update banner

The worker owns the banner lifecycle. `_sync_pending_banner` builds the card
body from the **exact** pending system-message text, formatted identically to
the initial prompt card (a fenced `System Prompt` section). There is no
truncation, no tools section, and no tool-mode section.

- **Pending** — created when a skill is added and anchored at
  `len(agent.messages)`, so it renders at the bottom of the transcript.
- **Reversed** — toggling the skill off recomputes `_pending_sys_message` to
  empty, so the pending banner is removed.
- **Tool-mode changes** — produce no pending text, so they never create or
  update a banner.
- **Committed** — `_do_start_turn` flips `pending=False` just before `run()`
  injects the system message. Committed banners stay anchored at their message
  index as later messages arrive.
- **Persisted** — `_do_persist` stores committed banners under
  `context_banners`; `ChatWorker.__init__` reloads them. Delete/regenerate
  prune or shift anchors. Pending (unsent) banners are not persisted.

The banner is a derived UI item — it is held on the chat
[`ChatWorker`](../modules/chat-worker.md), not in `chat.messages`.

## When no live chat exists

If the active chat has not been hydrated there is no live `Agent`, so
`_apply_live_config` returns after `_persist_config`, `_publish_config_summary`,
and `_update_config_chips`: the selections are saved and the panel counts
refresh, but no push or skill-update banner happens. The persisted config takes
effect the next time the chat is hydrated.
