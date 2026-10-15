# Tool approval flow

How a tool call's permission mode (`allow` / `ask` / `block`) is resolved on the
per-chat worker thread.

Related: [`chat-agent`](../modules/chat-agent.md), [`chat-worker`](../modules/chat-worker.md), [`qt-chat-controller`](../modules/qt-chat-controller.md), [`qt-chat-state`](../modules/qt-chat-state.md).

## Mode semantics

| Mode | Result |
|---|---|
| `allow` | execute immediately, no user interaction |
| `ask` | pause generation, show approval bar, wait for user |
| `block` | auto-deny with a message |

## Sequence

```
Worker thread (agent loop)                  GUI thread
──────────────────────────                  ──────────
Agent._resolve_tool_calls
   │  mode = self._tool_config.get(name, "ask")
   ├─ emit "tool_call" event (with mode) onto event_queue
   ▼
_pump → _handle_event
   │  if mode == "ask":
   │     emit approval_needed(chat_id, event) ──qt signal──►
   │                                                        _on_approval_needed
   │                                                          state.pending_tool_info = event
   │                                                          state.approval_text = "Approve X?"
   │                                                          show ApprovalBar
   │     (agent loop is awaiting its own approval queue)     ◄── user clicks Approve / Deny / Stop
   │◄── confirm_approval / deny_approval (call_soon_threadsafe)
   ▼
Agent.approve_tool(id) / deny_tool(id, reason)
   │  puts the decision on the per-tool asyncio.Queue
   ▼
_wait_for_approval returns the decision
   │  approve -> run_tool
   │  deny    -> "Tool execution denied by user." (+ feedback)
   ▼
emit "tool_result" → _handle_event appends it and emits approval_cleared
   │                                                        _on_approval_cleared → hide bar
   ▼
continue ReAct loop
```

## Agent-side decision (`_get_decision`)

```python
if mode == "block":  return ("deny", "Tool 'X' is blocked by user in current configuration.")
if mode == "allow":  return ("approve", None)
return await self._wait_for_approval(tool_id)   # ask
```

`_wait_for_approval` creates an `asyncio.Queue` keyed by `tool_id` in
`_pending_approvals` and awaits `queue.get()`. `approve_tool`/`deny_tool` (invoked
thread-safely via `call_soon_threadsafe`) put the decision onto that queue.
Decisions for all tools in one assistant message are gathered concurrently.

## Key structures

- `Agent._pending_approvals: dict[str, asyncio.Queue]` — tool_id → queue
  (worker loop only).
- `ChatState.pending_tool_info: dict` — the awaiting tool_call event (GUI).
- `ChatState.approval_text: str` — prompt shown in the approval bar (GUI).
- `ChatPanelModel.approvalVisible` / `approvalText` — per-panel QML-bound
  properties backed by `ChatController.chat_state_changed`.

Unlike the previous single-loop design, approval no longer blocks a consume loop:
the GUI handler returns immediately, and the worker's agent resumes when the
command arrives.
