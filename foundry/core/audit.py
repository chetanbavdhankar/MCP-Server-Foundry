"""
Audit logging for the Foundry pipeline and generated MCP servers.

Provides structured, append-only audit logs with:
- RFC 3339 timestamps in UTC
- Unique request/execution IDs for correlation
- Severity levels (INFO, WARN, ERROR, SECURITY)
- JSON Lines format for machine parseability
"""

import json
import hashlib
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


class AuditSeverity(str, Enum):
    """Audit log severity levels."""
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    SECURITY = "SECURITY"


class AuditEvent(str, Enum):
    """Predefined audit event types for consistent querying."""
    # Pipeline events
    PIPELINE_START = "pipeline.start"
    PIPELINE_COMPLETE = "pipeline.complete"
    PIPELINE_FAIL = "pipeline.fail"

    # Agent events
    AGENT_START = "agent.start"
    AGENT_COMPLETE = "agent.complete"
    AGENT_FAIL = "agent.fail"

    # Approval gate events
    GATE_PROMPT = "gate.prompt"
    GATE_APPROVED = "gate.approved"
    GATE_REJECTED = "gate.rejected"
    GATE_TIMEOUT = "gate.timeout"

    # Security events
    SECRET_DETECTED = "security.secret_detected"
    SEMGREP_PASS = "security.semgrep_pass"
    SEMGREP_FAIL = "security.semgrep_fail"
    INJECTION_BLOCKED = "security.injection_blocked"

    # Generated server runtime events (emitted by template code)
    TOOL_CALL = "runtime.tool_call"
    TOOL_RESULT = "runtime.tool_result"
    TOOL_ERROR = "runtime.tool_error"
    AUTH_FAILURE = "runtime.auth_failure"


@dataclass
class AuditEntry:
    """Single audit log entry. Serializes to one JSON line."""
    timestamp: str
    execution_id: str
    event: str
    severity: str
    agent: Optional[str] = None
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    duration_ms: Optional[float] = None

    def to_json(self) -> str:
        """Serialize to compact JSON, dropping None fields."""
        d = {k: v for k, v in asdict(self).items() if v is not None}
        return json.dumps(d, separators=(",", ":"))


class AuditLogger:
    """
    Append-only structured audit logger.

    Writes JSON Lines to a file. Each line is a self-contained AuditEntry.
    Thread-safe via append mode writes (atomic on POSIX for lines < PIPE_BUF).
    """

    def __init__(self, log_path: Path, execution_id: str):
        self.log_path = Path(log_path)
        self.execution_id = execution_id
        self._entries: List[AuditEntry] = []

        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        event: AuditEvent,
        severity: AuditSeverity = AuditSeverity.INFO,
        agent: Optional[str] = None,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
    ) -> AuditEntry:
        """Record an audit event."""
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            execution_id=self.execution_id,
            event=event.value,
            severity=severity.value,
            agent=agent,
            message=message,
            details=details,
            request_id=request_id,
            duration_ms=duration_ms,
        )
        self._entries.append(entry)
        self._flush(entry)
        return entry

    def _flush(self, entry: AuditEntry):
        """Append a single entry to the log file."""
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(entry.to_json() + "\n")

    @property
    def entries(self) -> List[AuditEntry]:
        """In-memory copy of all entries logged this session."""
        return list(self._entries)

    def get_entries_by_event(self, event: AuditEvent) -> List[AuditEntry]:
        """Filter entries by event type."""
        return [e for e in self._entries if e.event == event.value]


def compute_file_hash(file_path: Path) -> str:
    """SHA-256 hash of a file's contents for provenance tracking."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# Made with Bob
