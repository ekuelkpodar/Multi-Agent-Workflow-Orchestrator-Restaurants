"""API routes for the multi-agent system."""

from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

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

router = APIRouter()


# Request/Response Models


class StartConversationRequest(BaseModel):
    """Request to start a new conversation."""

    customer_id: UUID | None = None


class StartConversationResponse(BaseModel):
    """Response with new conversation details."""

    conversation_id: UUID
    message: str


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""

    message: str


class SendMessageResponse(BaseModel):
    """Response from the agent."""

    conversation_id: UUID
    agent_id: str
    message: str
    metadata: dict[str, Any] = {}


class ConversationStatusResponse(BaseModel):
    """Conversation status details."""

    conversation_id: UUID
    customer_id: UUID | None
    current_agent: str
    is_active: bool
    message_count: int


# Dependency to get conversation manager


async def get_conversation_manager() -> ConversationManager:
    """Get conversation manager instance."""
    state_manager = await get_state_manager()
    return ConversationManager(state_manager)


# Dependency to get agents


async def get_agents(
    conversation_manager: ConversationManager,
) -> dict[str, Any]:
    """Get all agent instances."""
    return {
        "orchestrator": OrchestratorAgent(conversation_manager),
        "order_agent": OrderAgent(conversation_manager),
        "inventory_agent": InventoryAgent(conversation_manager),
        "kitchen_agent": KitchenAgent(conversation_manager),
        "delivery_agent": DeliveryAgent(conversation_manager),
        "support_agent": SupportAgent(conversation_manager),
    }


# Routes


@router.post(
    "/conversations",
    response_model=StartConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_conversation(
    request: StartConversationRequest = StartConversationRequest(),
) -> StartConversationResponse:
    """
    Start a new conversation.

    Creates a new conversation and returns the conversation ID.
    """
    conversation_manager = await get_conversation_manager()

    # Create new conversation
    conversation = await conversation_manager.create_conversation(
        customer_id=request.customer_id
    )

    logger.info(
        "conversation_started",
        conversation_id=str(conversation.conversation_id),
        customer_id=str(request.customer_id) if request.customer_id else None,
    )

    return StartConversationResponse(
        conversation_id=conversation.conversation_id,
        message="Conversation started. How can I help you today?",
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=SendMessageResponse,
)
async def send_message(
    conversation_id: UUID,
    request: SendMessageRequest,
) -> SendMessageResponse:
    """
    Send a message in an existing conversation.

    The orchestrator will route the message to the appropriate agent.
    """
    conversation_manager = await get_conversation_manager()

    # Get conversation
    conversation = await conversation_manager.get_conversation(conversation_id)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    if not conversation.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation is not active",
        )

    # Initialize tracer
    tracer = AgentTracer(conversation_id)

    # Get all agents
    agents = await get_agents(conversation_manager)

    # Add user message to conversation
    await conversation_manager.add_message(
        conversation_id,
        MessageRole.USER,
        request.message,
    )

    # Get current agent (or orchestrator by default)
    current_agent_id = conversation.current_agent
    current_agent = agents.get(current_agent_id, agents["orchestrator"])

    # Let agent process the message
    context = conversation.context.copy()
    context["conversation_id"] = str(conversation_id)

    agent_response = await current_agent.think(
        message=request.message,
        conversation_id=conversation_id,
        context=context,
        tracer=tracer,
    )

    # Add agent response to conversation
    await conversation_manager.add_message(
        conversation_id,
        MessageRole.ASSISTANT,
        agent_response.message,
        agent_id=agent_response.agent_id,
    )

    # Handle handoff if needed
    if agent_response.handoff_to:
        await current_agent.handoff(
            target_agent=agent_response.handoff_to,
            conversation_id=conversation_id,
            reason=agent_response.handoff_reason or "Routing to specialist",
            context=context,
        )

        # If orchestrator, determine if we should immediately invoke next agent
        if current_agent_id == "orchestrator":
            next_agent = agents.get(agent_response.handoff_to)
            if next_agent:
                # Invoke next agent immediately
                next_response = await next_agent.think(
                    message=request.message,
                    conversation_id=conversation_id,
                    context=context,
                    tracer=tracer,
                )

                # Update response to be from the specialist
                agent_response = next_response

                # Add specialist response
                await conversation_manager.add_message(
                    conversation_id,
                    MessageRole.ASSISTANT,
                    next_response.message,
                    agent_id=next_response.agent_id,
                )

    logger.info(
        "message_processed",
        conversation_id=str(conversation_id),
        agent_id=agent_response.agent_id,
        tokens=agent_response.tokens_used,
    )

    return SendMessageResponse(
        conversation_id=conversation_id,
        agent_id=agent_response.agent_id,
        message=agent_response.message,
        metadata={
            "tokens_used": agent_response.tokens_used,
            "execution_time_ms": agent_response.execution_time_ms,
        },
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationStatusResponse,
)
async def get_conversation_status(
    conversation_id: UUID,
) -> ConversationStatusResponse:
    """Get the status of a conversation."""
    conversation_manager = await get_conversation_manager()

    conversation = await conversation_manager.get_conversation(conversation_id)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return ConversationStatusResponse(
        conversation_id=conversation.conversation_id,
        customer_id=conversation.customer_id,
        current_agent=conversation.current_agent,
        is_active=conversation.is_active,
        message_count=len(conversation.messages),
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def end_conversation(conversation_id: UUID) -> None:
    """End a conversation."""
    conversation_manager = await get_conversation_manager()

    await conversation_manager.end_conversation(conversation_id)

    logger.info("conversation_ended_via_api", conversation_id=str(conversation_id))


# Order endpoints


@router.get("/orders/{order_id}")
async def get_order_details(order_id: UUID) -> dict[str, Any]:
    """Get order details."""
    conversation_manager = await get_conversation_manager()
    agents = await get_agents(conversation_manager)

    support_agent = agents["support_agent"]

    # Use support agent's tool to get order details
    result = await support_agent.execute_tool(
        "get_order_details",
        {"order_id": order_id},
        conversation_id=uuid4(),  # Dummy conversation ID
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    return result.result


@router.get("/orders/{order_id}/tracking")
async def track_order(order_id: UUID) -> dict[str, Any]:
    """Get real-time order tracking."""
    conversation_manager = await get_conversation_manager()
    agents = await get_agents(conversation_manager)

    # Get kitchen status
    kitchen_agent = agents["kitchen_agent"]
    kitchen_result = await kitchen_agent.execute_tool(
        "get_order_eta",
        {"order_id": order_id},
        conversation_id=uuid4(),
    )

    # Get delivery status
    delivery_agent = agents["delivery_agent"]
    delivery_result = await delivery_agent.execute_tool(
        "get_delivery_eta",
        {"order_id": order_id},
        conversation_id=uuid4(),
    )

    return {
        "order_id": str(order_id),
        "kitchen_status": kitchen_result.result if kitchen_result.success else None,
        "delivery_status": delivery_result.result if delivery_result.success else None,
    }


# Admin endpoints


@router.get("/admin/agents/status")
async def get_agents_status() -> dict[str, Any]:
    """Get status of all agents (health check)."""
    conversation_manager = await get_conversation_manager()
    agents = await get_agents(conversation_manager)

    status_data = {
        "total_agents": len(agents),
        "agents": list(agents.keys()),
        "status": "healthy",
    }

    return status_data


@router.get("/admin/metrics")
async def get_metrics() -> dict[str, Any]:
    """Get system metrics."""
    # In production, return actual metrics from monitoring system
    return {
        "total_conversations": 0,
        "active_conversations": 0,
        "total_orders": 0,
        "avg_response_time_ms": 0,
        "agents": {
            "orchestrator": {"requests": 0, "avg_tokens": 0},
            "order_agent": {"requests": 0, "avg_tokens": 0},
            "inventory_agent": {"requests": 0, "avg_tokens": 0},
            "kitchen_agent": {"requests": 0, "avg_tokens": 0},
            "delivery_agent": {"requests": 0, "avg_tokens": 0},
            "support_agent": {"requests": 0, "avg_tokens": 0},
        },
    }


@router.post("/admin/inventory/update")
async def update_inventory(
    item_id: str,
    quantity: int,
    operation: str = "set",
) -> dict[str, Any]:
    """Manually update inventory levels."""
    conversation_manager = await get_conversation_manager()
    agents = await get_agents(conversation_manager)

    inventory_agent = agents["inventory_agent"]

    result = await inventory_agent.execute_tool(
        "update_stock",
        {"item_id": item_id, "quantity": quantity, "operation": operation},
        conversation_id=uuid4(),
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    return result.result
