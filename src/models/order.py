"""Order-related data models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    """Order status progression."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    READY = "ready"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class OrderItem(BaseModel):
    """Individual item in an order."""

    id: UUID = Field(default_factory=uuid4)
    item_id: str
    name: str
    quantity: int = Field(ge=1)
    unit_price: Decimal = Field(ge=0)
    customizations: list[str] = Field(default_factory=list)
    special_instructions: str | None = None
    subtotal: Decimal = Field(ge=0)

    def calculate_subtotal(self) -> Decimal:
        """Calculate subtotal for this item."""
        self.subtotal = self.unit_price * Decimal(self.quantity)
        return self.subtotal


class Order(BaseModel):
    """Complete order details."""

    id: UUID = Field(default_factory=uuid4)
    order_number: str | None = None
    customer_id: UUID
    conversation_id: UUID
    status: OrderStatus = OrderStatus.PENDING

    # Items
    items: list[OrderItem] = Field(default_factory=list)

    # Pricing
    subtotal: Decimal = Field(default=Decimal("0.00"), ge=0)
    tax: Decimal = Field(default=Decimal("0.00"), ge=0)
    delivery_fee: Decimal = Field(default=Decimal("0.00"), ge=0)
    discount: Decimal = Field(default=Decimal("0.00"), ge=0)
    total: Decimal = Field(default=Decimal("0.00"), ge=0)

    # Delivery details
    delivery_address: str | None = None
    delivery_instructions: str | None = None

    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    confirmed_at: datetime | None = None
    estimated_ready_at: datetime | None = None
    actual_ready_at: datetime | None = None
    estimated_delivery_at: datetime | None = None
    delivered_at: datetime | None = None

    # Assignments
    driver_id: UUID | None = None

    # Metadata
    promo_code: str | None = None
    notes: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    def calculate_totals(self, tax_rate: Decimal = Decimal("0.08")) -> None:
        """Calculate all order totals."""
        # Calculate subtotal from items
        self.subtotal = sum(item.subtotal for item in self.items)

        # Apply discount
        discounted_amount = self.subtotal - self.discount

        # Calculate tax on discounted amount
        self.tax = (discounted_amount * tax_rate).quantize(Decimal("0.01"))

        # Calculate total
        self.total = discounted_amount + self.tax + self.delivery_fee

    def add_item(self, item: OrderItem) -> None:
        """Add an item to the order."""
        item.calculate_subtotal()
        self.items.append(item)
        self.calculate_totals()
