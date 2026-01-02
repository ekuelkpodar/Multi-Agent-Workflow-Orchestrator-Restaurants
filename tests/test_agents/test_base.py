"""Tests for base agent functionality."""

import pytest

from src.agents.orchestrator import OrchestratorAgent
from src.models.conversation import ConversationState
from src.state.conversation import ConversationManager


@pytest.mark.asyncio
async def test_agent_initialization(conversation_manager: ConversationManager) -> None:
    """Test that agents initialize correctly."""
    agent = OrchestratorAgent(conversation_manager)

    assert agent.agent_id == "orchestrator"
    assert agent.conversation_manager == conversation_manager
    assert len(agent.tools) > 0


@pytest.mark.asyncio
async def test_agent_tool_registration(conversation_manager: ConversationManager) -> None:
    """Test that agent tools are registered."""
    agent = OrchestratorAgent(conversation_manager)

    # Check that tools are registered
    assert "classify_intent" in agent.tools
    assert "get_menu_info" in agent.tools
    assert "get_hours" in agent.tools


@pytest.mark.asyncio
async def test_agent_tool_execution(
    conversation_manager: ConversationManager,
    sample_conversation: ConversationState,
) -> None:
    """Test agent tool execution."""
    agent = OrchestratorAgent(conversation_manager)

    # Execute a tool
    result = await agent.execute_tool(
        "get_menu_info",
        {},
        sample_conversation.conversation_id,
    )

    assert result.success is True
    assert result.result is not None
    assert "categories" in result.result
