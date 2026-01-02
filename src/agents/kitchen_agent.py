"""Kitchen Agent - Manages food preparation queue and timing."""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from src.agents.base import BaseAgent
from src.models.order import OrderStatus
from src.state.conversation import ConversationManager
from src.state.manager import get_state_manager
from src.utils.prompts import PromptTemplates


class KitchenAgent(BaseAgent):
    """
    Kitchen agent that coordinates food preparation.

    Responsibilities:
    - Estimate prep times based on queue
    - Track order status through kitchen
    - Manage kitchen capacity
    - Provide accurate ETAs
    """

    def __init__(self, conversation_manager: ConversationManager):
        super().__init__("kitchen_agent", conversation_manager)
        self.register_tools()

        # Base prep times in minutes by category
        self.base_prep_times = {
            "pizza": 15,
            "burgers": 8,
            "salads": 5,
            "drinks": 1,
        }

    @property
    def system_prompt(self) -> str:
        """Return the kitchen agent system prompt."""
        return PromptTemplates.KITCHEN_AGENT_SYSTEM

    def register_tools(self) -> None:
        """Register kitchen agent tools."""
        self.register_tool("add_to_queue", self.add_to_queue)
        self.register_tool("get_queue_status", self.get_queue_status)
        self.register_tool("update_order_status", self.update_order_status)
        self.register_tool("get_order_eta", self.get_order_eta)
        self.register_tool("prioritize_order", self.prioritize_order)
        self.register_tool("estimate_prep_time", self.estimate_prep_time)

    async def add_to_queue(
        self,
        order_id: UUID,
        items: list[dict[str, Any]],
        priority: int = 0,
    ) -> dict[str, Any]:
        """
        Add an order to the kitchen queue.

        Args:
            order_id: Order identifier
            items: List of order items
            priority: Priority level (higher = more urgent)

        Returns:
            Queue position and estimated time
        """
        state_manager = await get_state_manager()

        # Calculate prep time
        total_prep_time = await self.estimate_prep_time(items)

        # Get current queue depth
        queue_depth = await self._get_queue_depth()

        # Calculate priority timestamp (lower = higher priority)
        current_time = datetime.utcnow()
        priority_timestamp = current_time.timestamp() - (priority * 1000)

        # Add to sorted set (Redis)
        await state_manager.zadd(
            "kitchen:queue",
            {str(order_id): priority_timestamp},
        )

        # Store order details
        order_data = {
            "status": OrderStatus.PREPARING.value,
            "items": items,
            "received_at": current_time.isoformat(),
            "estimated_ready": (
                current_time + timedelta(minutes=total_prep_time)
            ).isoformat(),
            "priority": priority,
        }

        await state_manager.set(
            f"kitchen:order:{order_id}",
            order_data,
            ttl=3600,  # 1 hour
        )

        # Start background simulation task
        asyncio.create_task(self._simulate_prep(order_id, total_prep_time))

        return {
            "order_id": str(order_id),
            "queue_position": queue_depth + 1,
            "estimated_prep_time_minutes": total_prep_time,
            "estimated_ready_at": order_data["estimated_ready"],
        }

    async def get_queue_status(self) -> dict[str, Any]:
        """
        Get current kitchen queue status.

        Returns:
            Queue depth and average wait time
        """
        queue_depth = await self._get_queue_depth()

        # Estimate average wait based on queue
        avg_wait_minutes = 5 + (queue_depth * 3)

        # Check if it's peak hours
        current_hour = datetime.utcnow().hour
        is_peak = (11 <= current_hour <= 13) or (18 <= current_hour <= 20)

        return {
            "queue_depth": queue_depth,
            "avg_wait_minutes": avg_wait_minutes,
            "is_peak_hours": is_peak,
            "status": "busy" if queue_depth > 5 else "normal",
        }

    async def update_order_status(
        self,
        order_id: UUID,
        status: str,
    ) -> dict[str, bool]:
        """
        Update the status of an order in the kitchen.

        Args:
            order_id: Order to update
            status: New status

        Returns:
            Success status
        """
        state_manager = await get_state_manager()
        order_key = f"kitchen:order:{order_id}"

        order_data = await state_manager.get(order_key)

        if not order_data:
            return {"success": False, "error": "Order not found"}

        order_data["status"] = status

        if status == "ready":
            order_data["actual_ready"] = datetime.utcnow().isoformat()
            # Remove from queue
            await state_manager.zrem("kitchen:queue", str(order_id))

        await state_manager.set(order_key, order_data, ttl=3600)

        return {"success": True, "status": status}

    async def get_order_eta(self, order_id: UUID) -> dict[str, Any]:
        """
        Get estimated time for order completion.

        Args:
            order_id: Order identifier

        Returns:
            ETA information
        """
        state_manager = await get_state_manager()
        order_key = f"kitchen:order:{order_id}"

        order_data = await state_manager.get(order_key)

        if not order_data:
            return {"error": "Order not found in kitchen"}

        status = order_data.get("status")
        estimated_ready = order_data.get("estimated_ready")

        if status == "ready":
            return {
                "status": "ready",
                "message": "Your order is ready for pickup!",
            }

        # Calculate remaining time
        if estimated_ready:
            ready_time = datetime.fromisoformat(estimated_ready)
            now = datetime.utcnow()
            remaining_minutes = max(0, int((ready_time - now).total_seconds() / 60))

            return {
                "status": status,
                "estimated_minutes_remaining": remaining_minutes,
                "estimated_ready_at": estimated_ready,
            }

        return {"status": status}

    async def prioritize_order(
        self,
        order_id: UUID,
        reason: str,
    ) -> dict[str, Any]:
        """
        Prioritize an order in the queue.

        Args:
            order_id: Order to prioritize
            reason: Reason for prioritization

        Returns:
            Updated queue position
        """
        state_manager = await get_state_manager()

        # Get current order data
        order_key = f"kitchen:order:{order_id}"
        order_data = await state_manager.get(order_key)

        if not order_data:
            return {"success": False, "error": "Order not found"}

        # Move to front of queue by setting very low timestamp
        priority_timestamp = datetime.utcnow().timestamp() - 10000

        await state_manager.zadd(
            "kitchen:queue",
            {str(order_id): priority_timestamp},
        )

        # Update order data
        order_data["priority"] = 100
        order_data["priority_reason"] = reason
        await state_manager.set(order_key, order_data, ttl=3600)

        return {
            "success": True,
            "message": f"Order prioritized: {reason}",
            "new_position": 1,
        }

    async def estimate_prep_time(self, items: list[dict[str, Any]]) -> int:
        """
        Estimate preparation time for a list of items.

        Args:
            items: List of order items

        Returns:
            Estimated prep time in minutes
        """
        total_time = 0
        item_count = len(items)

        for item in items:
            # Get category from item
            category = item.get("category", "other")

            # Get base time
            base_time = self.base_prep_times.get(category, 10)

            # Add customization time
            customizations = item.get("customizations", [])
            if customizations:
                base_time += 2

            # Add quantity multiplier
            quantity = item.get("quantity", 1)
            item_time = base_time * quantity

            total_time += item_time

        # Apply modifiers

        # Queue depth multiplier
        queue_depth = await self._get_queue_depth()
        queue_modifier = queue_depth * 2  # Each order ahead adds 2 minutes

        # Peak hours multiplier
        current_hour = datetime.utcnow().hour
        if (11 <= current_hour <= 13) or (18 <= current_hour <= 20):
            total_time = int(total_time * 1.3)

        # Large order modifier
        if item_count > 5:
            total_time += 5

        # Add queue time
        total_time += queue_modifier

        # Minimum 10 minutes
        return max(10, total_time)

    async def _get_queue_depth(self) -> int:
        """Get current number of orders in queue."""
        state_manager = await get_state_manager()
        queue = await state_manager.zrange("kitchen:queue", 0, -1)
        return len(queue) if queue else 0

    async def _simulate_prep(self, order_id: UUID, prep_time_minutes: int) -> None:
        """
        Simulate order preparation in the background.

        Args:
            order_id: Order being prepared
            prep_time_minutes: Estimated prep time
        """
        # Add realistic variance (+/- 20%)
        variance = random.uniform(0.8, 1.2)
        actual_time = int(prep_time_minutes * variance)

        # Wait for prep time (converted to seconds for simulation)
        # In production, this would be much longer
        # For demo, scale down by 60x (1 minute = 1 second)
        await asyncio.sleep(actual_time)

        # Update status to ready
        await self.update_order_status(order_id, "ready")

        self.logger.logger.info(
            "order_ready",
            order_id=str(order_id),
            actual_prep_time=actual_time,
        )
