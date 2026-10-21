"""Tool: create and control headless sub-agents through the local sub-agent server."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import traceback

import _client

_MODES = frozenset(("run", "spawn", "spawn_many", "wait", "status", "cancel"))


def _is_nested() -> bool:
    """Return whether this tool is running inside another sub-agent."""
    try:
        return int(os.environ.get("PROCOO_SUBAGENT_DEPTH", "0") or 0) > 0
    except ValueError:
        return True


def _build_spec(
    prompt: str,
    model: str,
    activated_skills: list[str] | None,
    tools: list[str] | None,
    tool_modes: dict | None,
    system_prompt: str,
    timeout: int,
) -> dict:
    """Assemble a sub-agent request, omitting empty optional fields.

    Args:
        prompt: The sub-agent task.
        model: Optional model name.
        activated_skills: Optional activated skill paths.
        tools: Optional explicit tool names.
        tool_modes: Optional per-tool mode overrides.
        system_prompt: Optional extra system instruction.
        timeout: Optional timeout in seconds.

    Returns:
        A request dict suitable for the HTTP API.
    """
    spec: dict = {"prompt": prompt}
    if model:
        spec["model"] = model
    if activated_skills:
        spec["activated_skills"] = activated_skills
    if tools:
        spec["tools"] = tools
    if tool_modes:
        spec["tool_modes"] = tool_modes
    if system_prompt:
        spec["system_prompt"] = system_prompt
    if timeout:
        spec["timeout"] = timeout
    return spec


def _dump(value: object) -> str:
    """Serialise a result to a compact JSON string.

    Args:
        value: Any JSON-serialisable value.

    Returns:
        The serialised string.
    """
    return json.dumps(value, ensure_ascii=False)


async def run(
    mode: str = "run",
    prompt: str = "",
    model: str = "",
    activated_skills: list[str] | None = None,
    tools: list[str] | None = None,
    tool_modes: dict | None = None,
    system_prompt: str = "",
    specs: list[dict] | None = None,
    agent_id: str = "",
    timeout: int = 0,
    wait: bool = False,
) -> str:
    """Create and control headless sub-agents that run one prompt independently.

    Sub-agents are separate agents with their own model, skills, and tools.
    They are headless: they cannot ask the user for tool approval, and nested
    sub-agents are disabled. Use `run` for a single blocking task, `spawn` +
    `wait` for long tasks, and `spawn_many` for simple batches. Records are
    kept in memory and disappear when the app exits.

    Args:
        mode: One of "run", "spawn", "spawn_many", "wait", "status", "cancel".
            Defaults to "run".
        prompt: The task for a single spawned sub-agent.
        model: Optional configured model name; empty uses the sub-agent default.
        activated_skills: Skill paths whose full instructions and tools the
            sub-agent receives.
        tools: Explicit tool names; empty uses every tool from activated_skills.
        tool_modes: Per-tool overrides, e.g. {"edit_file": "block"}.
        system_prompt: Optional extra instruction appended to the system prompt.
        specs: List of request objects for mode="spawn_many".
        agent_id: Target id for mode="wait", "status", or "cancel".
        timeout: Spawn timeout in seconds (0 uses the server default), or the
            maximum wait time for mode="wait".
        wait: For mode="spawn_many", block until every job finishes.

    Returns:
        A JSON string containing the record, records list, or an error object.
    """
    if _is_nested():
        return _dump(
            {
                "error": (
                    "Nested sub-agents are disabled. This tool cannot be used "
                    "from inside a sub-agent."
                )
            }
        )
    if mode not in _MODES:
        return _dump(
            {"error": (f"Unknown mode: {mode}. Valid modes: " + ", ".join(sorted(_MODES)))}
        )

    if isinstance(specs, str):
        try:
            specs = json.loads(specs)
        except (json.JSONDecodeError, TypeError):
            return _dump({"error": "specs must be a list of request objects."})
    if isinstance(tool_modes, str):
        try:
            tool_modes = json.loads(tool_modes)
        except (json.JSONDecodeError, TypeError):
            return _dump({"error": "tool_modes must be an object."})

    try:
        if mode == "run":
            if not prompt.strip():
                return _dump({"error": "mode='run' requires a non-empty prompt."})
            spec = _build_spec(
                prompt,
                model,
                activated_skills,
                tools,
                tool_modes,
                system_prompt,
                timeout or 540,
            )
            return _dump(await _client.run(spec))

        if mode == "spawn":
            if not prompt.strip():
                return _dump({"error": "mode='spawn' requires a non-empty prompt."})
            spec = _build_spec(
                prompt,
                model,
                activated_skills,
                tools,
                tool_modes,
                system_prompt,
                timeout,
            )
            return _dump(await _client.spawn(spec))

        if mode == "spawn_many":
            if not specs:
                return _dump({"error": "mode='spawn_many' requires a non-empty specs list."})
            records = await _client.spawn_many(specs, wait=wait)
            return _dump({"records": records})

        if mode == "wait":
            if not agent_id:
                return _dump({"error": "mode='wait' requires agent_id."})
            return _dump(await _client.wait(agent_id, timeout=timeout))

        if mode == "status":
            if agent_id:
                return _dump(await _client.get(agent_id))
            return _dump({"records": await _client.list_agents()})

        if not agent_id:
            return _dump({"error": "mode='cancel' requires agent_id."})
        return _dump(await _client.cancel(agent_id))
    except Exception:
        return _dump({"error": traceback.format_exc()})


if __name__ == "__main__":
    arguments = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    output = asyncio.run(run(**arguments))
    sys.stdout.buffer.write(output.encode("utf-8") + b"\n")
