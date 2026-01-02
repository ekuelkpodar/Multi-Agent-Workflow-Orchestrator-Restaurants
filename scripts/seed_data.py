"""Seed initial data for the restaurant system."""

import asyncio
from decimal import Decimal
from uuid import uuid4

from src.models.customer import Customer
from src.models.driver import Driver, DriverStatus, Location
from src.models.inventory import InventoryItem
from src.state.manager import StateManager


async def seed_menu_and_inventory() -> None:
    """Seed menu items and inventory."""
    print("Seeding menu and inventory...")

    state_manager = StateManager()
    await state_manager.connect()

    # Menu items with inventory
    menu_items = [
        InventoryItem(
            item_id="pizza_pepperoni",
            name="Pepperoni Pizza",
            category="pizza",
            quantity=50,
            low_stock_threshold=10,
            ingredients=["dough", "sauce", "cheese", "pepperoni"],
        ),
        InventoryItem(
            item_id="pizza_margherita",
            name="Margherita Pizza",
            category="pizza",
            quantity=45,
            low_stock_threshold=10,
            ingredients=["dough", "sauce", "cheese", "basil"],
        ),
        InventoryItem(
            item_id="pizza_veggie",
            name="Veggie Pizza",
            category="pizza",
            quantity=40,
            low_stock_threshold=10,
            ingredients=["dough", "sauce", "cheese", "vegetables"],
        ),
        InventoryItem(
            item_id="burger_cheese",
            name="Cheeseburger",
            category="burgers",
            quantity=30,
            low_stock_threshold=8,
            ingredients=["bun", "patty", "cheese", "lettuce"],
        ),
        InventoryItem(
            item_id="burger_chicken",
            name="Chicken Burger",
            category="burgers",
            quantity=25,
            low_stock_threshold=8,
            ingredients=["bun", "chicken", "lettuce", "mayo"],
        ),
        InventoryItem(
            item_id="burger_veggie",
            name="Veggie Burger",
            category="burgers",
            quantity=20,
            low_stock_threshold=8,
            ingredients=["bun", "veggie_patty", "lettuce"],
        ),
        InventoryItem(
            item_id="salad_caesar",
            name="Caesar Salad",
            category="salads",
            quantity=20,
            low_stock_threshold=5,
            ingredients=["lettuce", "caesar_dressing", "croutons"],
        ),
        InventoryItem(
            item_id="salad_greek",
            name="Greek Salad",
            category="salads",
            quantity=18,
            low_stock_threshold=5,
            ingredients=["lettuce", "feta", "olives", "tomatoes"],
        ),
        InventoryItem(
            item_id="drink_coke",
            name="Coca-Cola",
            category="drinks",
            quantity=100,
            low_stock_threshold=20,
            ingredients=[],
        ),
        InventoryItem(
            item_id="drink_water",
            name="Bottled Water",
            category="drinks",
            quantity=150,
            low_stock_threshold=30,
            ingredients=[],
        ),
    ]

    for item in menu_items:
        key = f"inventory:{item.item_id}"
        await state_manager.set(key, item.model_dump(mode="json"))
        print(f"  ✓ Added {item.name} (stock: {item.quantity})")

    await state_manager.disconnect()
    print("✓ Menu and inventory seeded successfully\n")


async def seed_drivers() -> None:
    """Seed driver pool."""
    print("Seeding drivers...")

    state_manager = StateManager()
    await state_manager.connect()

    drivers = [
        Driver(
            name="John Smith",
            status=DriverStatus.AVAILABLE,
            current_location=Location(lat=40.7128, lng=-74.0060),
            vehicle_type="car",
            rating=4.9,
        ),
        Driver(
            name="Maria Garcia",
            status=DriverStatus.AVAILABLE,
            current_location=Location(lat=40.7200, lng=-74.0100),
            vehicle_type="car",
            rating=4.8,
        ),
        Driver(
            name="Ahmed Khan",
            status=DriverStatus.AVAILABLE,
            current_location=Location(lat=40.7100, lng=-74.0050),
            vehicle_type="bike",
            rating=4.7,
        ),
        Driver(
            name="Sarah Johnson",
            status=DriverStatus.AVAILABLE,
            current_location=Location(lat=40.7150, lng=-74.0080),
            vehicle_type="scooter",
            rating=4.6,
        ),
        Driver(
            name="Carlos Rodriguez",
            status=DriverStatus.AVAILABLE,
            current_location=Location(lat=40.7180, lng=-74.0070),
            vehicle_type="car",
            rating=4.8,
        ),
    ]

    for i, driver in enumerate(drivers, 1):
        key = f"driver:{i}"
        await state_manager.set(key, driver.model_dump(mode="json"))
        print(f"  ✓ Added {driver.name} ({driver.vehicle_type}, rating: {driver.rating})")

    await state_manager.disconnect()
    print("✓ Drivers seeded successfully\n")


async def seed_sample_customers() -> None:
    """Seed sample customers."""
    print("Seeding sample customers...")

    state_manager = StateManager()
    await state_manager.connect()

    customers = [
        Customer(
            email="john.doe@example.com",
            phone="+1234567890",
            name="John Doe",
            default_address="123 Main St, New York, NY 10001",
            total_orders=15,
        ),
        Customer(
            email="jane.smith@example.com",
            phone="+1234567891",
            name="Jane Smith",
            default_address="456 Park Ave, New York, NY 10002",
            is_vip=True,
            total_orders=32,
        ),
        Customer(
            email="bob.wilson@example.com",
            phone="+1234567892",
            name="Bob Wilson",
            default_address="789 Broadway, New York, NY 10003",
            total_orders=8,
        ),
    ]

    for customer in customers:
        key = f"customer:{customer.id}"
        await state_manager.set(key, customer.model_dump(mode="json"))
        print(f"  ✓ Added {customer.name} (VIP: {customer.is_vip})")

    await state_manager.disconnect()
    print("✓ Sample customers seeded successfully\n")


async def main() -> None:
    """Run all seed functions."""
    print("\n" + "=" * 50)
    print("  Seeding Restaurant System Data")
    print("=" * 50 + "\n")

    await seed_menu_and_inventory()
    await seed_drivers()
    await seed_sample_customers()

    print("=" * 50)
    print("  ✓ All data seeded successfully!")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
