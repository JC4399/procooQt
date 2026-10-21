"""Sub-agent run logs — chat-style JSON transcripts written beside the skill."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import SubAgentRecord

RUN_LOG_SESSION = "subagent"


class SubAgentLogWriter:
    """Persist one sub-agent run as a chat-style JSON transcript.

    Attributes:
        log_dir: Directory that receives one JSON file per run.
    """

    def __init__(self, log_dir: str | Path) -> None:
        """Initialise the writer.

        Args:
            log_dir: Directory where run transcripts are stored.
        """
        self.log_dir = Path(log_dir)

    # ------------------------------------------------------------------
    #  Public: Write
    # ------------------------------------------------------------------

    def write(self, record: SubAgentRecord, messages: list[dict]) -> str:
        """Write the transcript atomically and return its absolute path.

        Args:
            record: The terminal sub-agent record.
            messages: The live ``agent.messages`` history captured at run end.

        Returns:
            The absolute path of the written JSON file.

        Raises:
            OSError: When the log directory or file cannot be written.
        """
        self.log_dir.mkdir(parents=True, exist_ok=True)
        path = self.log_dir / f"{record.id.replace(':', '_')}.json"
        data = self._build_payload(record, messages)
        tmp = path.parent / (path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, default=str)
        tmp.replace(path)
        return str(path.resolve())

    # ------------------------------------------------------------------
    #  Private: Payload
    # ------------------------------------------------------------------

    @staticmethod
    def _build_payload(record: SubAgentRecord, messages: list[dict]) -> dict:
        """Build the chat-compatible payload for one run.

        Args:
            record: The terminal sub-agent record.
            messages: The captured agent message history.

        Returns:
            A dict matching the keys used by ``storage/chats/*.json`` plus
            sub-agent metadata.
        """
        return {
            "id": record.id,
            "skills_config": {
                "activated": list(record.activated_skills),
                "tools": dict(record.tool_config),
            },
            "messages": list(messages),
            "session": RUN_LOG_SESSION,
            "created_at": record.created_at,
            "updated_at": record.finished_at,
            "message_count": len(messages),
            "model_name": record.model_name,
            "true_input_tokens": int(record.tokens.get("input", 0) or 0),
            "true_output_cum": int(record.tokens.get("output", 0) or 0),
            "status": record.status.value,
            "error": record.error,
            "spec": record.spec.model_dump(mode="json"),
        }
