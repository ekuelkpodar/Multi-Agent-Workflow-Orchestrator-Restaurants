"""Base agent class with common functionality for all agents."""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Callable
from uuid import UUID

from anthropic import Anthropic, AsyncAnthropic
from pydantic import BaseModel

from src.config import get_settings
from src.models.conversation import AgentResponse, HandoffResult, Message, MessageRole
from src.state.conversation import ConversationManager
from src.utils.logging import AgentLogger
from src.utils.tracing import AgentTracer


class ToolResult(BaseModel):
    """Result from a tool execution."""

    tool_name: str
    success: bool
    result: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0


class BaseAgent(ABC):
    """Base class for all specialized agents."""

    def __init__(
        self,
        agent_id: str,
        conversation_manager: ConversationManager,
    ):
        self.agent_id = agent_id
        self.conversation_manager = conversation_manager
        self.settings = get_settings()
        self.logger = AgentLogger(agent_id)

        # Initialize Anthropic client
        self.client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)

        # Tool registry
        self.tools: dict[str, Callable] = {}

        # Conversation history for this agent
        self.conversation_history: list[Message] = []

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass

    @abstractmethod
    def register_tools(self) -> None:
        """Register available tools for this agent."""
        pass

    async def think(
        self,
        message: str,
        conversation_id: UUID,
        context: dict[str, Any],
        tracer: AgentTracer | None = None,
    ) -> AgentResponse:
        """
        Process a message and generate a response.

        Args:
            message: User message to process
            conversation_id: ID of the conversation
            context: Additional context for the agent
            tracer: Optional tracer for monitoring

        Returns:
            AgentResponse with the agent's reply and metadata
        """
        start_time = time.time()

        try:
            # Get conversation history
            recent_messages = await self.conversation_manager.get_recent_messages(
                conversation_id, limit=10
            )

            # Build messages for Claude
            messages = self._build_message_history(recent_messages, message)

            # Make API call with retry logic
            response = await self._call_llm_with_retry(messages, context)

            # Parse response
            agent_response = self._parse_response(response)

            # Calculate metrics
            execution_time_ms = (time.time() - start_time) * 1000
            agent_response.execution_time_ms = execution_time_ms

            # Log the interaction
            self.logger.log_interaction(
                action="think",
                conversation_id=str(conversation_id),
                duration_ms=execution_time_ms,
                tokens=agent_response.tokens_used,
            )

            # Add to tracer if available
            if tracer:
                tracer.add_event(
                    "agent_response",
                    self.agent_id,
                    duration_ms=execution_time_ms,
                    tokens=agent_response.tokens_used,
                )

            return agent_response

        except Exception as e:
            self.logger.log_error(
                error=str(e),
                conversation_id=str(conversation_id),
            )
            raise

    async def execute_tool(
        self,
        tool_name: str,
        params: dict[str, Any],
        conversation_id: UUID,
    ) -> ToolResult:
        """
        Execute a registered tool.

        Args:
            tool_name: Name of the tool to execute
            params: Parameters for the tool
            conversation_id: ID of the conversation

        Returns:
            ToolResult with the execution outcome
        """
        start_time = time.time()

        if tool_name not in self.tools:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' not found",
            )

        try:
            # Execute the tool
            tool_func = self.tools[tool_name]
            result = await tool_func(**params)

            execution_time_ms = (time.time() - start_time) * 1000

            # Log the tool call
            self.logger.log_tool_call(
                tool_name=tool_name,
                conversation_id=str(conversation_id),
                duration_ms=execution_time_ms,
                success=True,
            )

            return ToolResult(
                tool_name=tool_name,
                success=True,
                result=result,
                execution_time_ms=execution_time_ms,
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000

            self.logger.log_tool_call(
                tool_name=tool_name,
                conversation_id=str(conversation_id),
                duration_ms=execution_time_ms,
                success=False,
                error=str(e),
            )

            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
                execution_time_ms=execution_time_ms,
            )

    async def handoff(
        self,
        target_agent: str,
        conversation_id: UUID,
        reason: str,
        context: dict[str, Any],
    ) -> HandoffResult:
        """
        Hand off the conversation to another agent.

        Args:
            target_agent: ID of the agent to hand off to
            conversation_id: ID of the conversation
            reason: Reason for the handoff
            context: Context to pass to the next agent

        Returns:
            HandoffResult with handoff details
        """
        handoff = HandoffResult(
            from_agent=self.agent_id,
            to_agent=target_agent,
            reason=reason,
            context=context,
        )

        # Record the handoff in conversation state
        await self.conversation_manager.add_handoff(conversation_id, handoff)

        # Log the handoff
        self.logger.log_handoff(
            to_agent=target_agent,
            conversation_id=str(conversation_id),
            reason=reason,
        )

        return handoff

    def get_conversation_history(self) -> list[Message]:
        """Get the conversation history for this agent."""
        return self.conversation_history.copy()

    def clear_context(self) -> None:
        """Clear the agent's conversation context."""
        self.conversation_history.clear()

    async def _call_llm_with_retry(
        self,
        messages: list[dict[str, str]],
        context: dict[str, Any],
    ) -> Any:
        """Call the LLM with exponential backoff retry logic."""
        max_retries = self.settings.max_retries
        retry_delay = self.settings.retry_delay

        for attempt in range(max_retries):
            try:
                response = await self.client.messages.create(
                    model=self.settings.anthropic_model,
                    max_tokens=self.settings.max_tokens,
                    system=self.system_prompt,
                    messages=messages,
                )
                return response

            except Exception as e:
                if attempt == max_retries - 1:
                    raise

                # Exponential backoff
                wait_time = retry_delay * (2**attempt)
                self.logger.logger.warning(
                    f"LLM call failed, retrying in {wait_time}s",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    error=str(e),
                )
                await asyncio.sleep(wait_time)

        raise Exception("Max retries exceeded")

    def _build_message_history(
        self,
        recent_messages: list[Message],
        current_message: str,
    ) -> list[dict[str, str]]:
        """Build message history for Claude API."""
        messages = []

        # Add recent conversation history
        for msg in recent_messages[-5:]:  # Last 5 messages for context
            if msg.role in [MessageRole.USER, MessageRole.ASSISTANT]:
                messages.append(
                    {
                        "role": msg.role.value,
                        "content": msg.content,
                    }
                )

        # Add current message
        messages.append(
            {
                "role": "user",
                "content": current_message,
            }
        )

        return messages

    def _parse_response(self, response: Any) -> AgentResponse:
        """Parse the LLM response into an AgentResponse."""
        # Extract the text content
        content = response.content[0].text if response.content else ""

        # Check for handoff indicators in the response
        handoff_to = None
        handoff_reason = None

        # Simple parsing - in production, use structured output
        if "HANDOFF:" in content:
            lines = content.split("\n")
            for line in lines:
                if line.startswith("HANDOFF:"):
                    handoff_to = line.split(":")[1].strip()
                elif line.startswith("REASON:"):
                    handoff_reason = line.split(":", 1)[1].strip()

        return AgentResponse(
            agent_id=self.agent_id,
            message=content,
            handoff_to=handoff_to,
            handoff_reason=handoff_reason,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
        )

    def register_tool(self, name: str, func: Callable) -> None:
        """Register a tool with the agent."""
        self.tools[name] = func
