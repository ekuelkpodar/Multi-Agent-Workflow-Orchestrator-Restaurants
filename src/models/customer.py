"""Customer-related models."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field


class Customer(BaseModel):
    """Customer profile."""

    id: UUID = Field(default_factory=uuid4)
    email: EmailStr | None = None
    phone: str | None = None
    name: str | None = None
    default_address: str | None = None
    is_vip: bool = False
    credit_balance: float = 0.0
    total_orders: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, str] = Field(default_factory=dict)


class CustomerHistory(BaseModel):
    """Customer order history summary."""

    customer_id: UUID
    total_orders: int
    total_spent: float
    avg_order_value: float
    last_order_date: datetime | None = None
    favorite_items: list[str] = Field(default_factory=list)
    complaint_count: int = 0
    refund_count: int = 0
