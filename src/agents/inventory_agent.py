"""Inventory Agent - Manages real-time stock levels and reservations."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.agents.base import BaseAgent
from src.models.inventory import InventoryItem, InventoryReservation
from src.state.conversation import ConversationManager
from src.state.manager import get_state_manager
from src.utils.prompts import PromptTemplates


class InventoryAgent(BaseAgent):
    """
    Inventory agent that manages stock levels and availability.

    Responsibilities:
    - Check real-time availability
    - Reserve inventory for pending orders
    - Suggest substitutions for unavailable items
    - Track low stock alerts
    """

    def __init__(self, conversation_manager: ConversationManager):
        super().__init__("inventory_agent", conversation_manager)
        self.register_tools()

    @property
    def system_prompt(self) -> str:
        """Return the inventory agent system prompt."""
        return PromptTemplates.INVENTORY_AGENT_SYSTEM

    def register_tools(self) -> None:
        """Register inventory agent tools."""
        self.register_tool("check_availability", self.check_availability)
        self.register_tool("reserve_inventory", self.reserve_inventory)
        self.register_tool("release_reservation", self.release_reservation)
        self.register_tool("get_substitutions", self.get_substitutions)
        self.register_tool("update_stock", self.update_stock)
        self.register_tool("get_low_stock_items", self.get_low_stock_items)

    async def _get_inventory_key(self, item_id: str) -> str:
        """Generate Redis key for inventory item."""
        return f"inventory:{item_id}"

    async def _get_reservation_key(self, reservation_id: UUID) -> str:
        """Generate Redis key for reservation."""
        return f"reservation:{reservation_id}"

    async def check_availability(
        self,
        item_id: str,
        quantity: int = 1,
    ) -> dict[str, Any]:
        """
        Check if an item is available in the requested quantity.

        Args:
            item_id: Item identifier
            quantity: Requested quantity

        Returns:
            Availability status and current stock
        """
        state_manager = await get_state_manager()
        key = await self._get_inventory_key(item_id)

        # Get current inventory
        inventory_data = await state_manager.get(key)

        if not inventory_data:
            # Initialize with default stock for demo
            inventory_data = await self._initialize_inventory(item_id)

        inventory = InventoryItem(**inventory_data)

        available = inventory.quantity >= quantity
        is_low_stock = inventory.is_low_stock

        return {
            "item_id": item_id,
            "available": available,
            "current_stock": inventory.quantity,
            "requested_quantity": quantity,
            "is_low_stock": is_low_stock,
        }

    async def reserve_inventory(
        self,
        item_id: str,
        quantity: int,
        order_id: UUID,
        ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        """
        Reserve inventory for a pending order.

        Args:
            item_id: Item to reserve
            quantity: Quantity to reserve
            order_id: Order ID for tracking
            ttl_seconds: Reservation TTL in seconds

        Returns:
            Reservation details
        """
        # Check availability first
        availability = await self.check_availability(item_id, quantity)

        if not availability["available"]:
            return {
                "success": False,
                "error": "Insufficient stock",
                "available_quantity": availability["current_stock"],
            }

        # Create reservation
        reservation = InventoryReservation(
            item_id=item_id,
            quantity=quantity,
            order_id=order_id,
            expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds),
        )

        # Save reservation to Redis
        state_manager = await get_state_manager()
        reservation_key = await self._get_reservation_key(reservation.reservation_id)
        await state_manager.set(
            reservation_key,
            reservation.model_dump(mode="json"),
            ttl=ttl_seconds,
        )

        # Decrement available stock (optimistic locking in production)
        await self._adjust_stock(item_id, -quantity)

        return {
            "success": True,
            "reservation_id": str(reservation.reservation_id),
            "expires_at": reservation.expires_at.isoformat(),
        }

    async def release_reservation(self, reservation_id: UUID) -> dict[str, bool]:
        """
        Release an inventory reservation.

        Args:
            reservation_id: Reservation to release

        Returns:
            Success status
        """
        state_manager = await get_state_manager()
        reservation_key = await self._get_reservation_key(reservation_id)

        # Get reservation
        reservation_data = await state_manager.get(reservation_key)

        if not reservation_data:
            return {"success": False, "error": "Reservation not found"}

        reservation = InventoryReservation(**reservation_data)

        # Return stock
        await self._adjust_stock(reservation.item_id, reservation.quantity)

        # Delete reservation
        await state_manager.delete(reservation_key)

        return {"success": True}

    async def get_substitutions(
        self,
        item_id: str,
        max_suggestions: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Get substitute items for an unavailable item.

        Args:
            item_id: Unavailable item
            max_suggestions: Maximum number of suggestions

        Returns:
            List of substitute items
        """
        # Get the original item's category
        state_manager = await get_state_manager()
        item_key = await self._get_inventory_key(item_id)
        item_data = await state_manager.get(item_key)

        if not item_data:
            return []

        original_item = InventoryItem(**item_data)
        category = original_item.category

        # Find items in the same category that are available
        # In production, query database
        # For now, use a simple mapping
        substitutions = []

        category_items = {
            "pizza": [
                ("pizza_margherita", "Margherita Pizza", Decimal("14.99")),
                ("pizza_pepperoni", "Pepperoni Pizza", Decimal("15.99")),
                ("pizza_veggie", "Veggie Pizza", Decimal("14.99")),
            ],
            "burgers": [
                ("burger_cheese", "Cheeseburger", Decimal("12.99")),
                ("burger_chicken", "Chicken Burger", Decimal("13.99")),
                ("burger_veggie", "Veggie Burger", Decimal("11.99")),
            ],
            "salads": [
                ("salad_caesar", "Caesar Salad", Decimal("9.99")),
                ("salad_greek", "Greek Salad", Decimal("10.99")),
                ("salad_garden", "Garden Salad", Decimal("8.99")),
            ],
        }

        if category in category_items:
            for alt_id, alt_name, alt_price in category_items[category]:
                if alt_id != item_id:
                    # Check if available
                    availability = await self.check_availability(alt_id)
                    if availability["available"]:
                        substitutions.append(
                            {
                                "item_id": alt_id,
                                "name": alt_name,
                                "price": float(alt_price),
                                "category": category,
                                "in_stock": availability["current_stock"],
                            }
                        )

                if len(substitutions) >= max_suggestions:
                    break

        return substitutions

    async def update_stock(
        self,
        item_id: str,
        quantity: int,
        operation: str = "set",
    ) -> dict[str, Any]:
        """
        Update stock level for an item.

        Args:
            item_id: Item to update
            quantity: Quantity to set or adjust
            operation: 'set', 'add', or 'subtract'

        Returns:
            Updated stock level
        """
        if operation == "set":
            state_manager = await get_state_manager()
            key = await self._get_inventory_key(item_id)
            inventory_data = await state_manager.get(key)

            if inventory_data:
                inventory = InventoryItem(**inventory_data)
                inventory.quantity = quantity
                inventory.last_updated = datetime.utcnow()
                await state_manager.set(key, inventory.model_dump(mode="json"))
                return {"item_id": item_id, "new_quantity": quantity}

        elif operation in ["add", "subtract"]:
            adjustment = quantity if operation == "add" else -quantity
            return await self._adjust_stock(item_id, adjustment)

        return {"error": "Invalid operation"}

    async def get_low_stock_items(self) -> list[dict[str, Any]]:
        """
        Get all items below their low stock threshold.

        Returns:
            List of low stock items
        """
        # In production, query database
        # For demo, check a few items
        low_stock = []

        test_items = [
            "pizza_pepperoni",
            "pizza_margherita",
            "burger_cheese",
            "salad_caesar",
        ]

        for item_id in test_items:
            availability = await self.check_availability(item_id)
            if availability.get("is_low_stock"):
                low_stock.append(
                    {
                        "item_id": item_id,
                        "current_stock": availability["current_stock"],
                    }
                )

        return low_stock

    async def _adjust_stock(self, item_id: str, adjustment: int) -> dict[str, Any]:
        """Adjust stock level by a delta amount."""
        state_manager = await get_state_manager()
        key = await self._get_inventory_key(item_id)

        inventory_data = await state_manager.get(key)

        if not inventory_data:
            inventory_data = await self._initialize_inventory(item_id)

        inventory = InventoryItem(**inventory_data)
        inventory.quantity += adjustment
        inventory.quantity = max(0, inventory.quantity)  # Don't go negative
        inventory.last_updated = datetime.utcnow()

        await state_manager.set(key, inventory.model_dump(mode="json"))

        return {"item_id": item_id, "new_quantity": inventory.quantity}

    async def _initialize_inventory(self, item_id: str) -> dict[str, Any]:
        """Initialize inventory for an item with default stock."""
        # Default stock levels for demo
        default_stock = {
            "pizza_pepperoni": 50,
            "pizza_margherita": 45,
            "burger_cheese": 30,
            "burger_chicken": 25,
            "salad_caesar": 20,
            "drink_coke": 100,
            "drink_water": 150,
        }

        category_map = {
            "pizza": "pizza",
            "burger": "burgers",
            "salad": "salads",
            "drink": "drinks",
        }

        # Determine category from item_id
        category = "other"
        for prefix, cat in category_map.items():
            if item_id.startswith(prefix):
                category = cat
                break

        inventory = InventoryItem(
            item_id=item_id,
            name=item_id.replace("_", " ").title(),
            category=category,
            quantity=default_stock.get(item_id, 50),
            low_stock_threshold=10,
        )

        # Save to Redis
        state_manager = await get_state_manager()
        key = await self._get_inventory_key(item_id)
        inventory_dict = inventory.model_dump(mode="json")
        await state_manager.set(key, inventory_dict)

        return inventory_dict
