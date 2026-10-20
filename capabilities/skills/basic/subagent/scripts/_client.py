"""Shared HTTP client for the local sub-agent server.

Not registered as a tool (leading underscore).  Import it from an
agent-authored batch script to spawn several sub-agents concurrently:

    import sys
    sys.path.insert(0, r"<skill-dir>/scripts")
    import asyncio
    import _client

    async def main() -> None:
        ids = await _client.spawn_many([{"prompt": "..."}, {"prompt": "..."}])
        results = await asyncio.gather(*(_client.wait(item["id"]) for item in ids))
        print(results)

    asyncio.run(main())

Connection settings come from ``PROCOO_SUBAGENT_URL`` /
``PROCOO_SUBAGENT_API_KEY``, then ``config/config.yaml``, then the defaults.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

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


def base_url() -> str:
    """Return the sub-agent server base URL without a trailing slash."""
    override = os.environ.get("PROCOO_SUBAGENT_URL", "").strip()
    if override:
        return override.rstrip("/")
    section = _load_config().get("subagent") or {}
    host = str(section.get("host", "127.0.0.1"))
    port = int(section.get("port", 12842))
    return f"http://{host}:{port}"


def api_key() -> str:
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
    key = api_key()
    return {"X-Api-Key": key} if key else {}


async def _request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    total: float | None = 30.0,
) -> dict[str, Any]:
    """Send one JSON request to the sub-agent server.

    Args:
        method: HTTP method.
        path: Path beginning with ``/``.
        payload: Optional JSON body.
        total: Total request timeout in seconds; ``None`` disables it.

    Returns:
        The decoded JSON response.

    Raises:
        RuntimeError: When the server returns an error response.
    """
    timeout = aiohttp.ClientTimeout(total=total, connect=10.0)
    url = f"{base_url()}{path}"
    async with (
        aiohttp.ClientSession(timeout=timeout) as session,
        session.request(method, url, json=payload, headers=_headers()) as response,
    ):
        text = await response.text()
        if response.status >= 400:
            raise RuntimeError(f"Sub-agent server HTTP {response.status}: {text[:1000]}")
        return await response.json()


def is_terminal(record: dict[str, Any]) -> bool:
    """Return whether a record is in a terminal state."""
    return str(record.get("status", "")) in ("done", "error", "cancelled")


async def spawn(spec: dict[str, Any]) -> dict[str, Any]:
    """Create and schedule one sub-agent.

    Args:
        spec: Sub-agent request (`prompt`, optional model/skills/tools/timeout).

    Returns:
        The queued record.
    """
    return await _request("POST", "/subagents", spec)


async def spawn_many(specs: list[dict[str, Any]], wait: bool = False) -> list[dict[str, Any]]:
    """Create and schedule several sub-agents in one request.

    Args:
        specs: List of sub-agent requests.
        wait: When true, block until every job finishes.

    Returns:
        The resulting records.

    Raises:
        RuntimeError: When the server rejects the batch.
    """
    response = await _request(
        "POST",
        "/subagents/batch",
        {"specs": specs, "wait": wait},
        total=None if wait else 30.0,
    )
    records = response.get("records", [])
    return records if isinstance(records, list) else []


async def wait(agent_id: str, timeout: float = 0) -> dict[str, Any]:
    """Poll one sub-agent until it reaches a terminal state.

    Args:
        agent_id: The sub-agent id.
        timeout: Maximum wait in seconds; ``0`` waits up to 540 seconds, just
            under the tool runner's subprocess limit.

    Returns:
        The terminal record.

    Raises:
        RuntimeError: When the job does not finish before *timeout*.
    """
    deadline = asyncio.get_running_loop().time() + (timeout or 540.0)
    while True:
        record = await _request("GET", f"/subagents/{quote(agent_id)}")
        if is_terminal(record):
            return record
        if asyncio.get_running_loop().time() >= deadline:
            raise RuntimeError(f"Sub-agent '{agent_id}' did not finish before the wait timeout.")
        await asyncio.sleep(0.5)


async def run(spec: dict[str, Any]) -> dict[str, Any]:
    """Create one sub-agent and block until it finishes.

    Args:
        spec: Sub-agent request.

    Returns:
        The terminal record.
    """
    return await _request("POST", "/subagents/run", spec, total=None)


async def list_agents(status: str = "") -> list[dict[str, Any]]:
    """Return retained sub-agent records.

    Args:
        status: Optional exact status filter.

    Returns:
        The matching records.
    """
    suffix = f"?status={quote(status)}" if status else ""
    response = await _request("GET", f"/subagents{suffix}")
    records = response.get("records", [])
    return records if isinstance(records, list) else []


async def get(agent_id: str) -> dict[str, Any]:
    """Return one sub-agent record without waiting.

    Args:
        agent_id: The sub-agent id.

    Returns:
        The current record.
    """
    return await _request("GET", f"/subagents/{quote(agent_id)}")


async def cancel(agent_id: str) -> dict[str, Any]:
    """Cancel one sub-agent.

    Args:
        agent_id: The sub-agent id.

    Returns:
        The updated record.
    """
    return await _request("POST", f"/subagents/{quote(agent_id)}/cancel")
