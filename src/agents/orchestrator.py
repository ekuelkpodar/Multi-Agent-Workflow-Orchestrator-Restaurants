"""Orchestrator Agent - Routes requests to appropriate specialist agents."""

from typing import Any
from uuid import UUID

from src.agents.base import BaseAgent
from src.state.conversation import ConversationManager
from src.utils.prompts import PromptTemplates


class OrchestratorAgent(BaseAgent):
    """
    Orchestrator agent that analyzes intent and routes to specialists.

    The orchestrator is the entry point for all customer requests.
    It classifies intent, manages conversation flow, and coordinates handoffs.
    """

    def __init__(self, conversation_manager: ConversationManager):
        super().__init__("orchestrator", conversation_manager)
        self.register_tools()

    @property
    def system_prompt(self) -> str:
        """Return the orchestrator system prompt."""
        return PromptTemplates.ORCHESTRATOR_SYSTEM

    def register_tools(self) -> None:
        """Register orchestrator tools."""
        self.register_tool("classify_intent", self.classify_intent)
        self.register_tool("get_menu_info", self.get_menu_info)
        self.register_tool("get_hours", self.get_hours)

    async def classify_intent(self, message: str) -> dict[str, Any]:
        """
        Classify the user's intent from their message.

        Args:
            message: User's message

        Returns:
            Dictionary with intent classification and confidence
        """
        # Simple keyword-based classification
        # In production, use Claude or a classifier model
        message_lower = message.lower()

        intents = {
            "new_order": [
                "order",
                "want",
                "get",
                "buy",
                "pizza",
                "burger",
                "food",
            ],
            "order_status": ["status", "where", "track", "eta", "when"],
            "modify_order": ["change", "modify", "update", "add to"],
            "cancel_order": ["cancel", "nevermind", "don't want"],
            "complaint": ["complaint", "problem", "issue", "wrong", "bad", "cold"],
            "refund_request": ["refund", "money back", "return"],
            "delivery_issue": ["delivery", "driver", "address", "location"],
        }

        # Calculate scores for each intent
        scores = {}
        for intent, keywords in intents.items():
            score = sum(1 for keyword in keywords if keyword in message_lower)
            if score > 0:
                scores[intent] = score

        # Default to general inquiry if no match
        if not scores:
            return {
                "intent": "general_inquiry",
                "confidence": 0.5,
                "suggested_agent": "orchestrator",
            }

        # Get highest scoring intent
        top_intent = max(scores.items(), key=lambda x: x[1])
        intent_name = top_intent[0]
        confidence = min(top_intent[1] / 3, 1.0)  # Normalize confidence

        # Map intent to agent
        agent_mapping = {
            "new_order": "order_agent",
            "order_status": "kitchen_agent",  # or delivery_agent based on status
            "modify_order": "order_agent",
            "cancel_order": "support_agent",
            "complaint": "support_agent",
            "refund_request": "support_agent",
            "delivery_issue": "delivery_agent",
            "general_inquiry": "orchestrator",
        }

        return {
            "intent": intent_name,
            "confidence": confidence,
            "suggested_agent": agent_mapping.get(intent_name, "orchestrator"),
        }

    async def get_menu_info(self) -> dict[str, Any]:
        """Get basic menu information."""
        # Simplified menu for now
        return {
            "categories": ["pizza", "burgers", "salads", "drinks"],
            "popular_items": [
                {"name": "Pepperoni Pizza", "price": 15.99},
                {"name": "Cheeseburger", "price": 12.99},
                {"name": "Caesar Salad", "price": 9.99},
            ],
            "message": "We have pizza, burgers, salads, and drinks. What would you like?",
        }

    async def get_hours(self) -> dict[str, str]:
        """Get restaurant operating hours."""
        return {
            "monday_friday": "11:00 AM - 10:00 PM",
            "saturday_sunday": "10:00 AM - 11:00 PM",
            "current_status": "open",
        }

    async def should_handoff(
        self,
        conversation_id: UUID,
        context: dict[str, Any],
    ) -> tuple[bool, str | None, str | None]:
        """
        Determine if the conversation should be handed off to another agent.

        Args:
            conversation_id: Current conversation ID
            context: Conversation context

        Returns:
            Tuple of (should_handoff, target_agent, reason)
        """
        # Get recent messages to understand context
        recent_messages = await self.conversation_manager.get_recent_messages(
            conversation_id, limit=3
        )

        if not recent_messages:
            return False, None, None

        # Get the latest user message
        last_message = recent_messages[-1].content if recent_messages else ""

        # Classify intent
        classification = await self.classify_intent(last_message)

        # If confidence is high and agent is not orchestrator, handoff
        if (
            classification["confidence"] > 0.6
            and classification["suggested_agent"] != "orchestrator"
        ):
            return (
                True,
                classification["suggested_agent"],
                f"User intent classified as: {classification['intent']}",
            )

        return False, None, None
