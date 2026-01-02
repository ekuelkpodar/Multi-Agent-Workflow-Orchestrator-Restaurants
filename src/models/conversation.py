"""Conversation and message models."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Message role types."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """Individual message in a conversation."""

    id: UUID = Field(default_factory=uuid4)
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    """Response from an agent."""

    agent_id: str
    message: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    handoff_to: str | None = None
    handoff_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tokens_used: int = 0
    execution_time_ms: float = 0.0


class HandoffResult(BaseModel):
    """Result of an agent handoff."""

    from_agent: str
    to_agent: str
    reason: str
    context: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    success: bool = True


class ConversationState(BaseModel):
    """Complete state of a conversation."""

    conversation_id: UUID = Field(default_factory=uuid4)
    customer_id: UUID | None = None
    current_agent: str = "orchestrator"
    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    context: dict[str, Any] = Field(default_factory=dict)
    messages: list[Message] = Field(default_factory=list)
    handoff_count: int = 0
    handoff_history: list[HandoffResult] = Field(default_factory=list)
    is_active: bool = True

    def add_message(self, role: MessageRole, content: str, agent_id: str | None = None) -> None:
        """Add a message to the conversation."""
        message = Message(role=role, content=content, agent_id=agent_id)
        self.messages.append(message)
        self.last_activity = datetime.utcnow()

    def add_handoff(self, handoff: HandoffResult) -> None:
        """Record an agent handoff."""
        self.handoff_history.append(handoff)
        self.handoff_count += 1
        self.current_agent = handoff.to_agent
        self.last_activity = datetime.utcnow()

    def get_recent_messages(self, limit: int = 10) -> list[Message]:
        """Get the most recent messages."""
        return self.messages[-limit:] if self.messages else []
