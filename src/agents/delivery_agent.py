"""Delivery Agent - Manages driver assignment and delivery tracking."""

import asyncio
import math
import random
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from src.agents.base import BaseAgent
from src.models.driver import Driver, DriverStatus, Location
from src.state.conversation import ConversationManager
from src.state.manager import get_state_manager
from src.utils.prompts import PromptTemplates


class DeliveryAgent(BaseAgent):
    """
    Delivery agent that manages driver assignment and delivery.

    Responsibilities:
    - Assign drivers to ready orders
    - Estimate delivery times
    - Track delivery progress
    - Handle delivery issues
    """

    def __init__(self, conversation_manager: ConversationManager):
        super().__init__("delivery_agent", conversation_manager)
        self.register_tools()

        # Restaurant location (default)
        self.restaurant_location = Location(lat=40.7128, lng=-74.0060)

    @property
    def system_prompt(self) -> str:
        """Return the delivery agent system prompt."""
        return PromptTemplates.DELIVERY_AGENT_SYSTEM

    def register_tools(self) -> None:
        """Register delivery agent tools."""
        self.register_tool("get_available_drivers", self.get_available_drivers)
        self.register_tool("assign_driver", self.assign_driver)
        self.register_tool("update_driver_status", self.update_driver_status)
        self.register_tool("get_delivery_eta", self.get_delivery_eta)
        self.register_tool("report_delivery_issue", self.report_delivery_issue)
        self.register_tool("get_driver_location", self.get_driver_location)

    async def get_available_drivers(
        self,
        kitchen_location: dict[str, float] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get list of available drivers with ETAs to kitchen.

        Args:
            kitchen_location: Optional kitchen location

        Returns:
            List of available drivers
        """
        if kitchen_location:
            location = Location(**kitchen_location)
        else:
            location = self.restaurant_location

        # Initialize driver pool if needed
        await self._ensure_driver_pool()

        state_manager = await get_state_manager()
        drivers = []

        # Get all drivers
        for i in range(1, 6):  # 5 drivers
            driver_key = f"driver:{i}"
            driver_data = await state_manager.get(driver_key)

            if driver_data:
                driver = Driver(**driver_data)

                if driver.is_available:
                    # Calculate distance/ETA
                    distance_km = self._calculate_distance(
                        location,
                        driver.current_location,
                    )
                    eta_minutes = int(distance_km * 3)  # 3 min per km

                    drivers.append(
                        {
                            "driver_id": str(driver.id),
                            "name": driver.name,
                            "vehicle_type": driver.vehicle_type,
                            "rating": driver.rating,
                            "distance_km": round(distance_km, 2),
                            "eta_minutes": eta_minutes,
                        }
                    )

        # Sort by distance (closest first)
        drivers.sort(key=lambda x: x["distance_km"])

        return drivers

    async def assign_driver(
        self,
        order_id: UUID,
        delivery_address: str,
        driver_id: UUID | None = None,
    ) -> dict[str, Any]:
        """
        Assign a driver to an order.

        Args:
            order_id: Order to deliver
            delivery_address: Delivery destination
            driver_id: Optional specific driver, otherwise auto-assign

        Returns:
            Assignment details with ETA
        """
        if driver_id is None:
            # Auto-assign closest available driver
            available = await self.get_available_drivers()

            if not available:
                return {
                    "success": False,
                    "error": "No drivers available",
                    "wait_time_minutes": 15,
                }

            # Get best driver (closest with rating > 4.0)
            best_driver = None
            for driver in available:
                if driver["rating"] >= 4.0:
                    best_driver = driver
                    break

            if not best_driver:
                best_driver = available[0]  # Fallback to closest

            driver_id = UUID(best_driver["driver_id"])

        # Update driver status
        state_manager = await get_state_manager()

        # Find driver key
        driver_key = None
        for i in range(1, 6):
            key = f"driver:{i}"
            driver_data = await state_manager.get(key)
            if driver_data and driver_data["id"] == str(driver_id):
                driver_key = key
                break

        if not driver_key:
            return {"success": False, "error": "Driver not found"}

        driver_data = await state_manager.get(driver_key)
        driver = Driver(**driver_data)

        # Assign the order
        driver.status = DriverStatus.ASSIGNED
        driver.current_order = order_id

        await state_manager.set(driver_key, driver.model_dump(mode="json"))

        # Calculate delivery ETA
        # Simplified: use geocoding in production
        delivery_eta = await self._calculate_delivery_eta(
            driver.current_location,
            delivery_address,
        )

        # Store delivery tracking info
        delivery_data = {
            "order_id": str(order_id),
            "driver_id": str(driver_id),
            "driver_name": driver.name,
            "status": "assigned",
            "pickup_location": self.restaurant_location.model_dump(),
            "delivery_address": delivery_address,
            "assigned_at": datetime.utcnow().isoformat(),
            "estimated_delivery_at": (
                datetime.utcnow() + timedelta(minutes=delivery_eta)
            ).isoformat(),
        }

        await state_manager.set(
            f"delivery:{order_id}",
            delivery_data,
            ttl=7200,  # 2 hours
        )

        # Start delivery simulation
        asyncio.create_task(self._simulate_delivery(order_id, driver_id, delivery_eta))

        return {
            "success": True,
            "driver_id": str(driver_id),
            "driver_name": driver.name,
            "vehicle_type": driver.vehicle_type,
            "estimated_delivery_minutes": delivery_eta,
            "estimated_delivery_at": delivery_data["estimated_delivery_at"],
        }

    async def update_driver_status(
        self,
        driver_id: UUID,
        status: str,
        location: dict[str, float] | None = None,
    ) -> dict[str, bool]:
        """
        Update driver status and location.

        Args:
            driver_id: Driver to update
            status: New status
            location: Optional new location

        Returns:
            Success status
        """
        state_manager = await get_state_manager()

        # Find driver
        driver_key = None
        for i in range(1, 6):
            key = f"driver:{i}"
            driver_data = await state_manager.get(key)
            if driver_data and driver_data["id"] == str(driver_id):
                driver_key = key
                break

        if not driver_key:
            return {"success": False}

        driver_data = await state_manager.get(driver_key)
        driver = Driver(**driver_data)

        # Update status
        driver.status = DriverStatus(status)

        if location:
            driver.current_location = Location(**location)

        # If completing delivery, increment counters
        if status == "available" and driver.current_order:
            driver.completed_today += 1
            driver.total_deliveries += 1
            driver.current_order = None

        await state_manager.set(driver_key, driver.model_dump(mode="json"))

        return {"success": True}

    async def get_delivery_eta(self, order_id: UUID) -> dict[str, Any]:
        """
        Get estimated delivery time for an order.

        Args:
            order_id: Order identifier

        Returns:
            ETA information
        """
        state_manager = await get_state_manager()
        delivery_key = f"delivery:{order_id}"

        delivery_data = await state_manager.get(delivery_key)

        if not delivery_data:
            return {"error": "Delivery not found"}

        status = delivery_data.get("status")
        estimated_delivery = delivery_data.get("estimated_delivery_at")

        if status == "delivered":
            return {
                "status": "delivered",
                "message": "Your order has been delivered!",
            }

        # Calculate remaining time
        if estimated_delivery:
            delivery_time = datetime.fromisoformat(estimated_delivery)
            now = datetime.utcnow()
            remaining_minutes = max(0, int((delivery_time - now).total_seconds() / 60))

            return {
                "status": status,
                "driver_name": delivery_data.get("driver_name"),
                "estimated_minutes_remaining": remaining_minutes,
                "estimated_delivery_at": estimated_delivery,
            }

        return {"status": status}

    async def report_delivery_issue(
        self,
        order_id: UUID,
        issue_type: str,
        description: str,
    ) -> dict[str, Any]:
        """
        Report a delivery issue.

        Args:
            order_id: Order with issue
            issue_type: Type of issue
            description: Issue description

        Returns:
            Issue ticket details
        """
        ticket_id = uuid4()

        issue_data = {
            "ticket_id": str(ticket_id),
            "order_id": str(order_id),
            "issue_type": issue_type,
            "description": description,
            "created_at": datetime.utcnow().isoformat(),
            "status": "open",
        }

        state_manager = await get_state_manager()
        await state_manager.set(
            f"issue:{ticket_id}",
            issue_data,
            ttl=86400,  # 24 hours
        )

        return {
            "ticket_id": str(ticket_id),
            "message": "Issue reported. Support team will contact you shortly.",
        }

    async def get_driver_location(self, driver_id: UUID) -> dict[str, Any]:
        """Get current location of a driver."""
        state_manager = await get_state_manager()

        for i in range(1, 6):
            key = f"driver:{i}"
            driver_data = await state_manager.get(key)
            if driver_data and driver_data["id"] == str(driver_id):
                location = driver_data.get("current_location")
                return {
                    "driver_id": str(driver_id),
                    "location": location,
                }

        return {"error": "Driver not found"}

    def _calculate_distance(self, loc1: Location, loc2: Location | None) -> float:
        """Calculate distance between two locations in km."""
        if not loc2:
            return 5.0  # Default

        # Haversine formula
        R = 6371  # Earth radius in km

        lat1, lng1 = math.radians(loc1.lat), math.radians(loc1.lng)
        lat2, lng2 = math.radians(loc2.lat), math.radians(loc2.lng)

        dlat = lat2 - lat1
        dlng = lng2 - lng1

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))

        return R * c

    async def _calculate_delivery_eta(
        self,
        driver_location: Location | None,
        delivery_address: str,
    ) -> int:
        """Calculate delivery ETA in minutes."""
        # Simplified calculation
        # In production, use Google Maps API or similar

        # Assume random distance between 1-8 km
        distance_km = random.uniform(1.0, 8.0)

        # Base: 3 minutes per km
        base_time = distance_km * 3

        # Traffic multiplier (random for simulation)
        traffic = random.choice([1.0, 1.3, 1.8])

        # Add pickup buffer
        total_time = (base_time * traffic) + 5

        return int(total_time)

    async def _ensure_driver_pool(self) -> None:
        """Initialize driver pool if not exists."""
        state_manager = await get_state_manager()

        # Check if drivers exist
        if await state_manager.exists("driver:1"):
            return

        # Create 5 drivers
        drivers = [
            {"name": "John Smith", "vehicle": "car", "rating": 4.9},
            {"name": "Maria Garcia", "vehicle": "car", "rating": 4.8},
            {"name": "Ahmed Khan", "vehicle": "bike", "rating": 4.7},
            {"name": "Sarah Johnson", "vehicle": "scooter", "rating": 4.6},
            {"name": "Carlos Rodriguez", "vehicle": "car", "rating": 4.8},
        ]

        for i, driver_info in enumerate(drivers, 1):
            driver = Driver(
                name=driver_info["name"],
                status=DriverStatus.AVAILABLE,
                current_location=Location(
                    lat=40.7128 + random.uniform(-0.05, 0.05),
                    lng=-74.0060 + random.uniform(-0.05, 0.05),
                ),
                vehicle_type=driver_info["vehicle"],
                rating=driver_info["rating"],
            )

            await state_manager.set(f"driver:{i}", driver.model_dump(mode="json"))

    async def _simulate_delivery(
        self,
        order_id: UUID,
        driver_id: UUID,
        eta_minutes: int,
    ) -> None:
        """Simulate delivery progress."""
        # Scale down for demo (1 minute = 1 second)
        await asyncio.sleep(eta_minutes)

        # Update delivery status
        state_manager = await get_state_manager()
        delivery_data = await state_manager.get(f"delivery:{order_id}")

        if delivery_data:
            delivery_data["status"] = "delivered"
            delivery_data["delivered_at"] = datetime.utcnow().isoformat()
            await state_manager.set(f"delivery:{order_id}", delivery_data, ttl=7200)

        # Update driver status
        await self.update_driver_status(driver_id, "available")

        self.logger.logger.info(
            "delivery_completed",
            order_id=str(order_id),
            driver_id=str(driver_id),
        )
