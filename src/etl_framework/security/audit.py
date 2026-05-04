"""Audit-log support for the framework itself.

Every code-generation, lineage publication and discovery run produces a
structured audit record. The records are intentionally append-only JSONL: they
are written to the artifact directory next to the generated code so that a
reviewer can answer "who generated this DAG and from which spec version".
"""

from __future__ import annotations

import getpass
import json
import os
import socket
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class AuditEvent:
    event: str
    entity: str | None
    spec_version: str | None
    actor: str = field(default_factory=getpass.getuser)
    host: str = field(default_factory=socket.gethostname)
    pid: int = field(default_factory=os.getpid)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    details: dict[str, str] = field(default_factory=dict)


class AuditLogger:
    """Append JSONL records to ``<root>/.audit.log``."""

    def __init__(self, root: str | Path):
        self.path = Path(root) / ".audit.log"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: AuditEvent) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")


def audit_event(event: str, entity: str | None = None, **details: str) -> AuditEvent:
    return AuditEvent(event=event, entity=entity, spec_version=None, details=details)
