"""Order Agent - Processes customer orders and manages order flow."""

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from src.agents.base import BaseAgent
from src.models.order import Order, OrderItem, OrderStatus
from src.state.conversation import ConversationManager
from src.utils.prompts import PromptTemplates


class OrderAgent(BaseAgent):
    """
    Order agent that handles the complete order flow.

    Responsibilities:
    - Parse natural language orders
    - Verify availability with Inventory Agent
    - Handle customizations
    - Calculate totals
    - Create and confirm orders
    """

    def __init__(self, conversation_manager: ConversationManager):
        super().__init__("order_agent", conversation_manager)
        self.register_tools()

        # Simple menu database (in production, this would be in PostgreSQL)
        self.menu = self._initialize_menu()

    @property
    def system_prompt(self) -> str:
        """Return the order agent system prompt."""
        return PromptTemplates.ORDER_AGENT_SYSTEM

    def register_tools(self) -> None:
        """Register order agent tools."""
        self.register_tool("get_menu", self.get_menu)
        self.register_tool("parse_order_items", self.parse_order_items)
        self.register_tool("calculate_total", self.calculate_total)
        self.register_tool("create_order", self.create_order)
        self.register_tool("validate_promo_code", self.validate_promo_code)

    def _initialize_menu(self) -> dict[str, dict[str, Any]]:
        """Initialize the menu catalog."""
        return {
            "pizza_pepperoni": {
                "name": "Pepperoni Pizza",
                "category": "pizza",
                "price": Decimal("15.99"),
                "sizes": ["small", "medium", "large"],
                "customizations": ["extra_cheese", "no_onions", "thin_crust"],
            },
            "pizza_margherita": {
                "name": "Margherita Pizza",
                "category": "pizza",
                "price": Decimal("14.99"),
                "sizes": ["small", "medium", "large"],
                "customizations": ["extra_cheese", "no_basil", "thin_crust"],
            },
            "burger_cheese": {
                "name": "Cheeseburger",
                "category": "burgers",
                "price": Decimal("12.99"),
                "sizes": ["regular", "double"],
                "customizations": ["no_onions", "no_pickles", "extra_cheese"],
            },
            "burger_chicken": {
                "name": "Chicken Burger",
                "category": "burgers",
                "price": Decimal("13.99"),
                "sizes": ["regular"],
                "customizations": ["spicy", "no_mayo", "extra_sauce"],
            },
            "salad_caesar": {
                "name": "Caesar Salad",
                "category": "salads",
                "price": Decimal("9.99"),
                "sizes": ["regular", "large"],
                "customizations": ["no_croutons", "extra_dressing", "add_chicken"],
            },
            "drink_coke": {
                "name": "Coca-Cola",
                "category": "drinks",
                "price": Decimal("2.99"),
                "sizes": ["regular", "large"],
                "customizations": [],
            },
            "drink_water": {
                "name": "Bottled Water",
                "category": "drinks",
                "price": Decimal("1.99"),
                "sizes": ["regular"],
                "customizations": [],
            },
        }

    async def get_menu(self, category: str | None = None) -> dict[str, Any]:
        """
        Get the menu or items from a specific category.

        Args:
            category: Optional category filter

        Returns:
            Menu items
        """
        if category:
            items = {
                k: v for k, v in self.menu.items() if v["category"] == category
            }
        else:
            items = self.menu

        # Format for display
        formatted_items = []
        for item_id, item_data in items.items():
            formatted_items.append(
                {
                    "id": item_id,
                    "name": item_data["name"],
                    "price": float(item_data["price"]),
                    "category": item_data["category"],
                }
            )

        return {"items": formatted_items, "count": len(formatted_items)}

    async def parse_order_items(self, order_text: str) -> list[dict[str, Any]]:
        """
        Parse natural language order into structured items.

        Args:
            order_text: Natural language order description

        Returns:
            List of parsed order items
        """
        # Simple parsing logic (in production, use Claude or NLP)
        items = []
        order_lower = order_text.lower()

        # Extract quantities
        import re

        quantity_pattern = r"(\d+)\s+(\w+)"
        matches = re.findall(quantity_pattern, order_lower)

        for qty, item_name in matches:
            # Try to match to menu items
            for item_id, item_data in self.menu.items():
                if item_name in item_data["name"].lower():
                    items.append(
                        {
                            "item_id": item_id,
                            "name": item_data["name"],
                            "quantity": int(qty),
                            "unit_price": float(item_data["price"]),
                        }
                    )
                    break

        # If no quantities found, check for item names
        if not items:
            for item_id, item_data in self.menu.items():
                if item_data["name"].lower() in order_lower:
                    items.append(
                        {
                            "item_id": item_id,
                            "name": item_data["name"],
                            "quantity": 1,
                            "unit_price": float(item_data["price"]),
                        }
                    )

        return items

    async def calculate_total(
        self,
        items: list[dict[str, Any]],
        promo_code: str | None = None,
    ) -> dict[str, Any]:
        """
        Calculate order total with tax and fees.

        Args:
            items: List of order items
            promo_code: Optional promo code

        Returns:
            Breakdown of costs
        """
        # Calculate subtotal
        subtotal = Decimal("0.00")
        for item in items:
            item_total = Decimal(str(item["unit_price"])) * item["quantity"]
            subtotal += item_total

        # Apply discount if promo code valid
        discount = Decimal("0.00")
        if promo_code:
            promo_result = await self.validate_promo_code(promo_code)
            if promo_result["valid"]:
                discount = subtotal * Decimal(str(promo_result["discount_percent"])) / 100

        # Calculate tax (8%)
        taxable_amount = subtotal - discount
        tax = (taxable_amount * Decimal("0.08")).quantize(Decimal("0.01"))

        # Delivery fee
        delivery_fee = Decimal("4.99")

        # Total
        total = taxable_amount + tax + delivery_fee

        return {
            "subtotal": float(subtotal),
            "discount": float(discount),
            "tax": float(tax),
            "delivery_fee": float(delivery_fee),
            "total": float(total),
        }

    async def create_order(
        self,
        customer_id: UUID,
        conversation_id: UUID,
        items: list[dict[str, Any]],
        delivery_address: str,
        promo_code: str | None = None,
        special_instructions: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a new order.

        Args:
            customer_id: Customer ID
            conversation_id: Conversation ID
            items: List of order items
            delivery_address: Delivery address
            promo_code: Optional promo code
            special_instructions: Special delivery instructions

        Returns:
            Created order details
        """
        # Create order object
        order = Order(
            customer_id=customer_id,
            conversation_id=conversation_id,
            delivery_address=delivery_address,
            notes=special_instructions,
            promo_code=promo_code,
            status=OrderStatus.PENDING,
        )

        # Add items
        for item_data in items:
            order_item = OrderItem(
                item_id=item_data["item_id"],
                name=item_data["name"],
                quantity=item_data["quantity"],
                unit_price=Decimal(str(item_data["unit_price"])),
                customizations=item_data.get("customizations", []),
                special_instructions=item_data.get("special_instructions"),
            )
            order_item.calculate_subtotal()
            order.items.append(order_item)

        # Calculate totals
        order.calculate_totals()

        # Generate order number
        order.order_number = f"ORD-{order.id.hex[:8].upper()}"

        # In production, save to database
        # For now, just return the order
        return {
            "order_id": str(order.id),
            "order_number": order.order_number,
            "status": order.status.value,
            "total": float(order.total),
            "estimated_delivery_time": 45,  # minutes
        }

    async def validate_promo_code(self, promo_code: str) -> dict[str, Any]:
        """
        Validate a promotional code.

        Args:
            promo_code: Promo code to validate

        Returns:
            Validation result with discount info
        """
        # Simple promo code validation (in production, check database)
        valid_promos = {
            "WELCOME10": {"discount_percent": 10, "description": "10% off first order"},
            "SAVE20": {"discount_percent": 20, "description": "20% off"},
            "FREESHIP": {"discount_percent": 0, "free_delivery": True},
        }

        promo_upper = promo_code.upper()

        if promo_upper in valid_promos:
            promo = valid_promos[promo_upper]
            return {
                "valid": True,
                "discount_percent": promo.get("discount_percent", 0),
                "free_delivery": promo.get("free_delivery", False),
                "description": promo["description"],
            }

        return {
            "valid": False,
            "error": "Invalid promo code",
        }
