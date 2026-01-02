"""Conversation state tracking and management."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from src.config import get_settings
from src.models.conversation import ConversationState, HandoffResult, Message, MessageRole
from src.state.manager import StateManager
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ConversationManager:
    """Manages conversation state persistence."""

    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.settings = get_settings()

    def _conversation_key(self, conversation_id: UUID) -> str:
        """Generate Redis key for a conversation."""
        return f"conversation:{conversation_id}"

    async def create_conversation(
        self,
        customer_id: UUID | None = None,
    ) -> ConversationState:
        """Create a new conversation."""
        conversation = ConversationState(customer_id=customer_id)

        await self.save_conversation(conversation)

        logger.info(
            "conversation_created",
            conversation_id=str(conversation.conversation_id),
            customer_id=str(customer_id) if customer_id else None,
        )

        return conversation

    async def get_conversation(self, conversation_id: UUID) -> ConversationState | None:
        """Retrieve a conversation by ID."""
        key = self._conversation_key(conversation_id)
        data = await self.state.get(key)

        if not data:
            return None

        # Reconstruct the conversation state
        conversation = ConversationState(**data)
        return conversation

    async def save_conversation(self, conversation: ConversationState) -> None:
        """Save conversation state to Redis."""
        key = self._conversation_key(conversation.conversation_id)

        # Convert to dict for storage
        data = conversation.model_dump(mode="json")

        # Save with TTL
        await self.state.set(
            key,
            data,
            ttl=self.settings.conversation_ttl,
        )

    async def add_message(
        self,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
        agent_id: str | None = None,
    ) -> None:
        """Add a message to the conversation."""
        conversation = await self.get_conversation(conversation_id)

        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        conversation.add_message(role, content, agent_id)
        await self.save_conversation(conversation)

        logger.debug(
            "message_added",
            conversation_id=str(conversation_id),
            role=role,
            agent_id=agent_id,
        )

    async def add_handoff(
        self,
        conversation_id: UUID,
        handoff: HandoffResult,
    ) -> None:
        """Record an agent handoff."""
        conversation = await self.get_conversation(conversation_id)

        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        conversation.add_handoff(handoff)
        await self.save_conversation(conversation)

        logger.info(
            "handoff_recorded",
            conversation_id=str(conversation_id),
            from_agent=handoff.from_agent,
            to_agent=handoff.to_agent,
            reason=handoff.reason,
        )

    async def update_context(
        self,
        conversation_id: UUID,
        context_updates: dict[str, Any],
    ) -> None:
        """Update conversation context."""
        conversation = await self.get_conversation(conversation_id)

        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        conversation.context.update(context_updates)
        conversation.last_activity = datetime.utcnow()

        await self.save_conversation(conversation)

    async def end_conversation(self, conversation_id: UUID) -> None:
        """Mark a conversation as ended."""
        conversation = await self.get_conversation(conversation_id)

        if not conversation:
            return

        conversation.is_active = False
        await self.save_conversation(conversation)

        logger.info("conversation_ended", conversation_id=str(conversation_id))

    async def get_recent_messages(
        self,
        conversation_id: UUID,
        limit: int = 10,
    ) -> list[Message]:
        """Get recent messages from a conversation."""
        conversation = await self.get_conversation(conversation_id)

        if not conversation:
            return []

        return conversation.get_recent_messages(limit)

    async def cleanup_expired_conversations(self) -> int:
        """Clean up conversations that haven't been active."""
        # This would be run periodically by a background task
        # For now, Redis TTL handles cleanup automatically
        logger.info("cleanup_check_completed")
        return 0
