"""Driver and delivery models."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DriverStatus(str, Enum):
    """Driver status states."""

    AVAILABLE = "available"
    ASSIGNED = "assigned"
    DELIVERING = "delivering"
    OFFLINE = "offline"


class Location(BaseModel):
    """Geographic location."""

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class Driver(BaseModel):
    """Delivery driver profile."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    status: DriverStatus = DriverStatus.OFFLINE
    current_location: Location | None = None
    current_order: UUID | None = None
    vehicle_type: str = "car"
    rating: float = Field(default=5.0, ge=0, le=5)
    completed_today: int = 0
    total_deliveries: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, str] = Field(default_factory=dict)

    @property
    def is_available(self) -> bool:
        """Check if driver is available for assignment."""
        return self.status == DriverStatus.AVAILABLE and self.current_order is None
