from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_AUDIT_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ToolAuditLog:
    """Local JSONL audit trail for Celeste tool decisions.

    Arguments and tool outputs are intentionally not recorded here. Some tools may
    later carry email bodies, private messages or other sensitive content; the
    audit log records what capability ran and its outcome, not the private data.
    """

    def __init__(self, brain_dir: Path):
        self.path = brain_dir / ".celeste" / "tool-audit.jsonl"

    def append(
        self,
        *,
        tool: str,
        risk: str,
        status: str,
        confirmation_id: str | None = None,
        summary: str | None = None,
    ) -> None:
        record: dict[str, Any] = {
            "time_utc": _utc_now(),
            "tool": tool,
            "risk": risk,
            "status": status,
        }
        if confirmation_id:
            record["confirmation_id"] = confirmation_id
        if summary:
            record["summary"] = summary[:500]

        with _AUDIT_LOCK:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        with _AUDIT_LOCK:
            if not self.path.exists():
                return []
            lines = self.path.read_text(encoding="utf-8").splitlines()

        records: list[dict[str, Any]] = []
        for line in reversed(lines[-limit:]):
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                records.append(item)
        return records
