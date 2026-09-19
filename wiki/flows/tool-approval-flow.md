# Tool approval flow

How a tool call's permission mode (`allow` / `ask` / `block`) is resolved.

Related: [`session-agent`](../modules/session-agent.md), [`qt-chat-controller`](../modules/qt-chat-controller.md), [`qt-session-state`](../modules/qt-session-state.md).

## Mode semantics

| Mode | Result |
|---|---|
| `allow` | execute immediately, no user interaction |
| `ask` | pause generation, show approval bar, wait for user |
| `block` | auto-deny with a message |

## Sequence

```
Agent._resolve_tool_calls
   │  mode = self._tool_config.get(name, "ask")
   ├─ emit "tool_call" event (with mode)
   ▼
ChatController._consume_events receives "tool_call"
   │  if mode == "ask":
   ▼
_handle_approval(session_id, event, state)
   │  state.approval_event = asyncio.Event()
   │  state.pending_tool_info = event
   │  state.approval_text = f"Approve {name}?"
   │  _refresh_sidebar; _rebuild_chat_display
   │  _set_approval_visible(True)  → ApprovalBar.qml visible
   │  await state.approval_event.wait()        ◄── blocks here
   ▼
user clicks Approve / Deny / Stop (ApprovalBar.qml / ChatPanel.qml)
   │
   ├─ chat._handle_approve    → _approve → session.approve_tool(id)
   │                                       + state.approval_event.set()
   ├─ chat._handle_deny(text) → _deny    → session.deny_tool(id, reason)
   │                                       + state.approval_event.set()
   └─ chat._handle_stop       → _stop_generation → session.deny_tool(id)
                                       + event.set() + active_task.cancel()
   │
   ▼  event.set() releases _handle_approval
   │
   ▼
back in Agent._resolve_tool_calls
   │  _wait_for_approval returned a decision
   │  approve -> run_tool
   │  deny    -> result "Tool execution denied by user." (+ optional feedback)
   ▼
_record_tool_result + continue ReAct loop
```

## Agent-side decision (`_get_decision`)

```python
if mode == "block":  return ("deny", "Tool 'X' is blocked by user in current configuration.")
if mode == "allow":  return ("approve", None)
return await self._wait_for_approval(tool_id)   # ask
```

`_wait_for_approval` creates an `asyncio.Queue` keyed by `tool_id` in
`_pending_approvals` and awaits `queue.get()`. `approve_tool`/`deny_tool` put
the decision onto that queue. Decisions for all tools in one assistant message
are gathered concurrently with `asyncio.gather`, so several `ask` tools can be
pending at once.

## Key structures

- `Agent._pending_approvals: dict[str, asyncio.Queue]` — tool_id → queue.
- `SessionState.approval_event: asyncio.Event` — gates the consume loop.
- `SessionState.pending_tool_info: dict` — the awaiting tool_call event.
- `SessionState.approval_text: str` — prompt shown in the approval bar.
- `ChatController.approvalVisible` / `approvalText` — QML-bound properties
  backed by `approval_visibility_changed`.
