"""Structured logging configuration."""

import logging
import sys
from typing import Any

import structlog
from pythonjsonlogger import jsonlogger

from src.config import get_settings


def setup_logging() -> None:
    """Configure structured logging for the application."""
    settings = get_settings()

    # Configure standard library logging
    log_level = getattr(logging, settings.log_level)

    if settings.log_format == "json":
        # JSON logging for production
        handler = logging.StreamHandler(sys.stdout)
        formatter = jsonlogger.JsonFormatter(
            fmt="%(timestamp)s %(level)s %(name)s %(message)s",
            rename_fields={"levelname": "level", "asctime": "timestamp"},
        )
        handler.setFormatter(formatter)
    else:
        # Human-readable logging for development
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer() if settings.log_format == "json"
            else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


class AgentLogger:
    """Specialized logger for agent interactions."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.logger = get_logger(agent_id)

    def log_interaction(
        self,
        action: str,
        conversation_id: str,
        duration_ms: float | None = None,
        tokens: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Log an agent interaction with structured data."""
        log_data = {
            "agent_id": self.agent_id,
            "conversation_id": conversation_id,
            "action": action,
        }

        if duration_ms is not None:
            log_data["duration_ms"] = duration_ms
        if tokens is not None:
            log_data["tokens"] = tokens

        log_data.update(kwargs)
        self.logger.info("agent_interaction", **log_data)

    def log_handoff(
        self,
        to_agent: str,
        conversation_id: str,
        reason: str,
        **kwargs: Any,
    ) -> None:
        """Log an agent handoff."""
        self.logger.info(
            "agent_handoff",
            agent_id=self.agent_id,
            to_agent=to_agent,
            conversation_id=conversation_id,
            reason=reason,
            **kwargs,
        )

    def log_tool_call(
        self,
        tool_name: str,
        conversation_id: str,
        duration_ms: float,
        success: bool,
        **kwargs: Any,
    ) -> None:
        """Log a tool invocation."""
        self.logger.info(
            "tool_call",
            agent_id=self.agent_id,
            tool_name=tool_name,
            conversation_id=conversation_id,
            duration_ms=duration_ms,
            success=success,
            **kwargs,
        )

    def log_error(
        self,
        error: str,
        conversation_id: str,
        **kwargs: Any,
    ) -> None:
        """Log an error."""
        self.logger.error(
            "agent_error",
            agent_id=self.agent_id,
            conversation_id=conversation_id,
            error=error,
            **kwargs,
        )
