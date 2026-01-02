"""WebSocket handlers for real-time communication."""

import json
from typing import Any
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError

from src.agents import (
    DeliveryAgent,
    InventoryAgent,
    KitchenAgent,
    OrchestratorAgent,
    OrderAgent,
    SupportAgent,
)
from src.models.conversation import MessageRole
from src.state.conversation import ConversationManager
from src.state.manager import get_state_manager
from src.utils.logging import get_logger
from src.utils.tracing import AgentTracer

logger = get_logger(__name__)


class WebSocketMessage(BaseModel):
    """WebSocket message format."""

    type: str  # "message", "status", "typing"
    content: str | None = None
    metadata: dict[str, Any] = {}


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, conversation_id: str, websocket: WebSocket) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        self.active_connections[conversation_id] = websocket
        logger.info("websocket_connected", conversation_id=conversation_id)

    def disconnect(self, conversation_id: str) -> None:
        """Remove a WebSocket connection."""
        if conversation_id in self.active_connections:
            del self.active_connections[conversation_id]
            logger.info("websocket_disconnected", conversation_id=conversation_id)

    async def send_message(
        self,
        conversation_id: str,
        message: dict[str, Any],
    ) -> None:
        """Send a message to a specific connection."""
        if conversation_id in self.active_connections:
            websocket = self.active_connections[conversation_id]
            await websocket.send_json(message)

    async def send_typing_indicator(
        self,
        conversation_id: str,
        agent_id: str,
    ) -> None:
        """Send typing indicator."""
        await self.send_message(
            conversation_id,
            {
                "type": "typing",
                "agent_id": agent_id,
                "content": "typing...",
            },
        )


# Global connection manager
manager = ConnectionManager()


async def handle_websocket_conversation(
    websocket: WebSocket,
    conversation_id: UUID,
) -> None:
    """
    Handle WebSocket connection for a conversation.

    Args:
        websocket: WebSocket connection
        conversation_id: Conversation identifier
    """
    conversation_str = str(conversation_id)

    # Initialize dependencies
    state_manager = await get_state_manager()
    conversation_manager = ConversationManager(state_manager)

    # Get or create conversation
    conversation = await conversation_manager.get_conversation(conversation_id)

    if not conversation:
        # Create new conversation
        conversation = await conversation_manager.create_conversation()
        conversation_id = conversation.conversation_id
        conversation_str = str(conversation_id)

    # Initialize agents
    agents = {
        "orchestrator": OrchestratorAgent(conversation_manager),
        "order_agent": OrderAgent(conversation_manager),
        "inventory_agent": InventoryAgent(conversation_manager),
        "kitchen_agent": KitchenAgent(conversation_manager),
        "delivery_agent": DeliveryAgent(conversation_manager),
        "support_agent": SupportAgent(conversation_manager),
    }

    # Accept connection
    await manager.connect(conversation_str, websocket)

    # Send welcome message
    await websocket.send_json(
        {
            "type": "connected",
            "conversation_id": conversation_str,
            "message": "Connected! How can I help you today?",
        }
    )

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()

            try:
                # Parse message
                message_data = json.loads(data)
                ws_message = WebSocketMessage(**message_data)

                if ws_message.type == "message" and ws_message.content:
                    # Process user message
                    await process_websocket_message(
                        conversation_id=conversation_id,
                        message=ws_message.content,
                        conversation_manager=conversation_manager,
                        agents=agents,
                        websocket=websocket,
                    )

                elif ws_message.type == "ping":
                    # Respond to ping
                    await websocket.send_json({"type": "pong"})

            except ValidationError as e:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Invalid message format",
                        "details": str(e),
                    }
                )

            except Exception as e:
                logger.error(
                    "websocket_message_error",
                    conversation_id=conversation_str,
                    error=str(e),
                )
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Failed to process message",
                    }
                )

    except WebSocketDisconnect:
        manager.disconnect(conversation_str)
        logger.info("websocket_client_disconnected", conversation_id=conversation_str)

    except Exception as e:
        logger.error(
            "websocket_error",
            conversation_id=conversation_str,
            error=str(e),
        )
        manager.disconnect(conversation_str)


async def process_websocket_message(
    conversation_id: UUID,
    message: str,
    conversation_manager: ConversationManager,
    agents: dict[str, Any],
    websocket: WebSocket,
) -> None:
    """
    Process a message received via WebSocket.

    Args:
        conversation_id: Conversation ID
        message: User message
        conversation_manager: Conversation manager
        agents: Dictionary of agent instances
        websocket: WebSocket connection
    """
    # Get conversation
    conversation = await conversation_manager.get_conversation(conversation_id)

    if not conversation:
        await websocket.send_json(
            {
                "type": "error",
                "message": "Conversation not found",
            }
        )
        return

    # Initialize tracer
    tracer = AgentTracer(conversation_id)

    # Add user message
    await conversation_manager.add_message(
        conversation_id,
        MessageRole.USER,
        message,
    )

    # Get current agent
    current_agent_id = conversation.current_agent
    current_agent = agents.get(current_agent_id, agents["orchestrator"])

    # Send typing indicator
    await manager.send_typing_indicator(str(conversation_id), current_agent_id)

    # Process with agent
    context = conversation.context.copy()
    context["conversation_id"] = str(conversation_id)

    agent_response = await current_agent.think(
        message=message,
        conversation_id=conversation_id,
        context=context,
        tracer=tracer,
    )

    # Add agent response
    await conversation_manager.add_message(
        conversation_id,
        MessageRole.ASSISTANT,
        agent_response.message,
        agent_id=agent_response.agent_id,
    )

    # Send response to client
    await websocket.send_json(
        {
            "type": "message",
            "agent_id": agent_response.agent_id,
            "content": agent_response.message,
            "metadata": {
                "tokens_used": agent_response.tokens_used,
                "execution_time_ms": agent_response.execution_time_ms,
            },
        }
    )

    # Handle handoff if needed
    if agent_response.handoff_to:
        await current_agent.handoff(
            target_agent=agent_response.handoff_to,
            conversation_id=conversation_id,
            reason=agent_response.handoff_reason or "Routing to specialist",
            context=context,
        )

        # Notify client of handoff
        await websocket.send_json(
            {
                "type": "handoff",
                "from_agent": current_agent_id,
                "to_agent": agent_response.handoff_to,
                "reason": agent_response.handoff_reason,
            }
        )

        # If orchestrator, immediately invoke next agent
        if current_agent_id == "orchestrator":
            next_agent = agents.get(agent_response.handoff_to)
            if next_agent:
                # Send typing indicator for new agent
                await manager.send_typing_indicator(
                    str(conversation_id),
                    agent_response.handoff_to,
                )

                # Process with specialist
                next_response = await next_agent.think(
                    message=message,
                    conversation_id=conversation_id,
                    context=context,
                    tracer=tracer,
                )

                # Add response
                await conversation_manager.add_message(
                    conversation_id,
                    MessageRole.ASSISTANT,
                    next_response.message,
                    agent_id=next_response.agent_id,
                )

                # Send specialist response
                await websocket.send_json(
                    {
                        "type": "message",
                        "agent_id": next_response.agent_id,
                        "content": next_response.message,
                        "metadata": {
                            "tokens_used": next_response.tokens_used,
                            "execution_time_ms": next_response.execution_time_ms,
                        },
                    }
                )
