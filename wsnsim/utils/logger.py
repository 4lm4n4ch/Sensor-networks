"""Trace logging utilities for simulation debugging and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TraceRecord:
    """Single trace log record."""

    wall_time: str
    sim_time: float
    message: str
    details: dict[str, Any] = field(default_factory=dict)


class TraceLogger:
    """Simple in-memory trace recorder with enable/disable controls."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.records: list[TraceRecord] = []

    def enable(self) -> None:
        """Enable tracing."""
        self.enabled = True

    def disable(self) -> None:
        """Disable tracing."""
        self.enabled = False

    def clear(self) -> None:
        """Clear buffered trace records."""
        self.records.clear()

    def log(self, sim_time: float, message: str, **details: Any) -> None:
        """Append a new trace event when enabled."""

        if not self.enabled:
            return

        self.records.append(
            TraceRecord(
                wall_time=datetime.now(timezone.utc).isoformat(),
                sim_time=float(sim_time),
                message=message,
                details=details,
            )
        )
