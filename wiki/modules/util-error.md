# util.error — exception hierarchy

Source: `procooQt/src/util/error/types.py`

## Purpose

Defines a small application exception hierarchy. Every exception carries a
**brief** message (shown in a Qt toast) and a **detail** message (logged to
the terminal). If only one is supplied, the other defaults to it, so
`ConfigError("Missing key")` works without setting both.

## Deliverables

- `ProcooError` base class + six subclasses (`ConfigError`, `AgentError`,
  `ToolError`, `ChatError`, `AutomationError`, `SubAgentError`), each tagged
  with a `category` string.
- Instances that carry `.brief`, `.detail`, and `.category` attributes.

## Function Reference

### `ProcooError`

| | |
|---|---|
| Signature | `class ProcooError(Exception)` |
| Attributes | `brief` (`str`), `detail` (`str`), `category` (`str = "general"`). |

### `ProcooError.__init__`

| | |
|---|---|
| Signature | `def __init__(self, brief: str = "", detail: str \| None = None, *, category: str \| None = None) -> None` |
| Inputs | `brief` — short UI message; `detail` — full log message (defaults to `brief`); `category` — optional domain tag. |
| Output | `None` |
| Side effects | sets `self.brief`, `self.detail`, `self.category`; calls `super().__init__(self.detail)`. |

### Subclasses

| Class | `category` | Raised when |
|---|---|---|
| `ConfigError` | `"config"` | a required config key is missing/invalid |
| `AgentError` | `"agent"` | the LLM agent fails during generation |
| `ToolError` | `"tool"` | a tool cannot be loaded/executed |
| `ChatError` | `"chat"` | a chat operation fails |
| `AutomationError` | `"automation"` | an automation cannot be loaded/run, or its headless agent reports an error |
| `SubAgentError` | `"subagent"` | a sub-agent request is invalid or cannot be run |
