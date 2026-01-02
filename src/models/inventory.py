"""Inventory management models."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class InventoryItem(BaseModel):
    """Inventory item with stock levels."""

    item_id: str
    name: str
    category: str
    quantity: int = Field(ge=0)
    unit: str = "count"
    low_stock_threshold: int = 10
    reorder_point: int = 20
    ingredients: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_low_stock(self) -> bool:
        """Check if item is low on stock."""
        return self.quantity <= self.low_stock_threshold

    @property
    def is_available(self) -> bool:
        """Check if item is available."""
        return self.quantity > 0


class InventoryReservation(BaseModel):
    """Temporary inventory reservation for pending orders."""

    reservation_id: UUID = Field(default_factory=uuid4)
    item_id: str
    quantity: int = Field(ge=1)
    order_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    is_active: bool = True

    def is_expired(self) -> bool:
        """Check if reservation has expired."""
        return datetime.utcnow() > self.expires_at
