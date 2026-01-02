"""Agent interaction tracing and monitoring."""

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generator
from uuid import UUID

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TraceEvent:
    """Individual trace event in the agent workflow."""

    timestamp: datetime
    event_type: str
    agent_id: str
    conversation_id: UUID
    duration_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentTracer:
    """Traces agent interactions throughout a conversation."""

    def __init__(self, conversation_id: UUID):
        self.conversation_id = conversation_id
        self.events: list[TraceEvent] = []
        self.start_time = time.time()

    def add_event(
        self,
        event_type: str,
        agent_id: str,
        duration_ms: float | None = None,
        **metadata: Any,
    ) -> None:
        """Add a trace event."""
        event = TraceEvent(
            timestamp=datetime.utcnow(),
            event_type=event_type,
            agent_id=agent_id,
            conversation_id=self.conversation_id,
            duration_ms=duration_ms,
            metadata=metadata,
        )
        self.events.append(event)

        # Log the event
        logger.info(
            "trace_event",
            conversation_id=str(self.conversation_id),
            event_type=event_type,
            agent_id=agent_id,
            duration_ms=duration_ms,
            **metadata,
        )

    @contextmanager
    def trace_operation(
        self, operation: str, agent_id: str, **metadata: Any
    ) -> Generator[None, None, None]:
        """Context manager to trace an operation with timing."""
        start = time.time()
        try:
            yield
        finally:
            duration_ms = (time.time() - start) * 1000
            self.add_event(operation, agent_id, duration_ms=duration_ms, **metadata)

    def get_trace_summary(self) -> dict[str, Any]:
        """Get a summary of the trace."""
        total_duration = (time.time() - self.start_time) * 1000

        agent_stats: dict[str, dict[str, Any]] = {}
        for event in self.events:
            if event.agent_id not in agent_stats:
                agent_stats[event.agent_id] = {
                    "event_count": 0,
                    "total_duration_ms": 0.0,
                }

            agent_stats[event.agent_id]["event_count"] += 1
            if event.duration_ms:
                agent_stats[event.agent_id]["total_duration_ms"] += event.duration_ms

        return {
            "conversation_id": str(self.conversation_id),
            "total_duration_ms": total_duration,
            "total_events": len(self.events),
            "agent_stats": agent_stats,
            "events": [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "event_type": event.event_type,
                    "agent_id": event.agent_id,
                    "duration_ms": event.duration_ms,
                    "metadata": event.metadata,
                }
                for event in self.events
            ],
        }
