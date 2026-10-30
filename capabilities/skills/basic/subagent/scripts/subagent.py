"""Tool: run one headless sub-agent through the local sub-agent server."""

from __future__ import annotations

import asyncio
from functools import lru_cache
import json
import os
from pathlib import Path
import sys
from typing import Any

import aiohttp
import yaml

_DEFAULT_URL = "http://127.0.0.1:12842"


@lru_cache(maxsize=1)
def _load_config() -> dict[str, Any]:
    """Find and load the project ``config/config.yaml``.

    Returns:
        The parsed config mapping, or an empty dict when no file is found.
    """
    for directory in [Path.cwd(), *Path(__file__).resolve().parents]:
        config_path = directory / "config" / "config.yaml"
        if config_path.is_file():
            try:
                with open(config_path, encoding="utf-8") as handle:
                    data = yaml.safe_load(handle)
            except (OSError, yaml.YAMLError):
                return {}
            return data if isinstance(data, dict) else {}
    return {}


def _base_url() -> str:
    """Return the sub-agent server base URL without a trailing slash."""
    override = os.environ.get("PROCOO_SUBAGENT_URL", "").strip()
    if override:
        return override.rstrip("/")
    section = _load_config().get("subagent") or {}
    host = str(section.get("host", "127.0.0.1"))
    port = int(section.get("port", 12842))
    return f"http://{host}:{port}"


def _api_key() -> str:
    """Return the configured API key, or an empty string when auth is open."""
    override = os.environ.get("PROCOO_SUBAGENT_API_KEY", "").strip()
    if override:
        return override
    config = _load_config()
    section = config.get("subagent") or {}
    keys = section.get("api_keys")
    if not keys:
        keys = (config.get("auth") or {}).get("api_keys") or []
    return str(keys[0]) if keys else ""


def _headers() -> dict[str, str]:
    """Build request headers, including the API key when configured."""
    key = _api_key()
    return {"X-Api-Key": key} if key else {}


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
    images: list[str] | None,
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
        images: Optional list of data-URL images attached to the first user
            message. Each entry should be a complete data URL such as
            ``"data:image/webp;base64,..."``.

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
    if images:
        spec["images"] = list(images)
    return spec


async def _post(spec: dict) -> dict[str, Any]:
    """Send one run request and return the decoded response.

    Args:
        spec: The sub-agent request.

    Returns:
        The response dict with ``text``, ``error``, and ``log_path``.

    Raises:
        RuntimeError: When the server returns an error response.
    """
    timeout = aiohttp.ClientTimeout(total=None, connect=10.0)
    url = f"{_base_url()}/subagents/run"
    async with (
        aiohttp.ClientSession(timeout=timeout) as session,
        session.post(url, json=spec, headers=_headers()) as response,
    ):
        text = await response.text()
        if response.status >= 400:
            raise RuntimeError(f"Sub-agent server HTTP {response.status}: {text[:1000]}")
        data = await response.json()
    return data if isinstance(data, dict) else {}


def _format_result(result: dict[str, Any]) -> str:
    """Format a run response as the answer plus a log-path hint.

    Args:
        result: The response dict from the server.

    Returns:
        The answer text and, when available, the transcript path.
    """
    text = str(result.get("text") or "").strip()
    error = str(result.get("error") or "").strip()
    body = f"{error}\n\n{text}".strip() if error and text else (error or text)
    log_path = str(result.get("log_path") or "").strip()
    if log_path:
        return f"{body}\n\nLog: {log_path}".strip()
    return body


async def run(
    prompt: str = "",
    model: str = "",
    activated_skills: list[str] | None = None,
    tools: list[str] | None = None,
    tool_modes: dict | None = None,
    system_prompt: str = "",
    timeout: int = 0,
    images: list[str] | None = None,
) -> str:
    """Run one headless sub-agent and wait for its final answer.

    The sub-agent is a separate agent with its own model, skills, and tools.
    It is headless: it cannot ask the user for tool approval, and nested
    sub-agents are disabled. The full reasoning and tool history is written to
    a JSON log beside the skill; only the final answer and that log path are
    returned.

    Args:
        prompt: The task for the sub-agent.
        model: Optional configured model name; empty uses the sub-agent default.
        activated_skills: Skill paths whose full instructions and tools the
            sub-agent receives.
        tools: Explicit tool names; empty uses every tool from activated_skills.
        tool_modes: Per-tool overrides, e.g. {"edit_file": "block"}.
        system_prompt: Optional extra instruction appended to the system prompt.
        timeout: Run timeout in seconds; 0 uses the server default.
        images: Optional list of data-URL images (e.g.
            ``"data:image/webp;base64,..."``) attached to the sub-agent's first
            user message. The multimodal model sees the image on its first
            reasoning step; no extra ``read_file`` round-trip is needed.

    Returns:
        The final answer followed by the transcript log path.
    """
    if _is_nested():
        return "Nested sub-agents are disabled. This tool cannot be used from inside a sub-agent."
    if not prompt.strip():
        return "Sub-agent prompt is empty."

    if isinstance(tool_modes, str):
        try:
            tool_modes = json.loads(tool_modes)
        except (json.JSONDecodeError, TypeError):
            return "tool_modes must be a JSON object."

    spec = _build_spec(
        prompt,
        model,
        activated_skills,
        tools,
        tool_modes,
        system_prompt,
        timeout or 540,
        images,
    )
    try:
        return _format_result(await _post(spec))
    except Exception as error:
        return f"Sub-agent failed: {error}"


if __name__ == "__main__":
    arguments = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    output = asyncio.run(run(**arguments))
    sys.stdout.buffer.write(output.encode("utf-8") + b"\n")
