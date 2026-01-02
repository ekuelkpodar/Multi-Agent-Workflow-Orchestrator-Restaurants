"""Pytest configuration and fixtures."""

import asyncio
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient

from src.main import app
from src.models.conversation import ConversationState
from src.models.customer import Customer
from src.models.driver import Driver, DriverStatus, Location
from src.models.inventory import InventoryItem
from src.models.order import Order, OrderItem, OrderStatus
from src.state.conversation import ConversationManager
from src.state.manager import StateManager


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def state_manager() -> AsyncGenerator[StateManager, None]:
    """Create a test state manager."""
    manager = StateManager()
    await manager.connect()
    yield manager
    await manager.disconnect()


@pytest_asyncio.fixture
async def conversation_manager(
    state_manager: StateManager,
) -> AsyncGenerator[ConversationManager, None]:
    """Create a test conversation manager."""
    manager = ConversationManager(state_manager)
    yield manager


@pytest_asyncio.fixture
async def test_client() -> AsyncGenerator[AsyncClient, None]:
    """Create a test HTTP client."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


# Sample data fixtures


@pytest.fixture
def sample_customer() -> Customer:
    """Create a sample customer."""
    return Customer(
        email="test@example.com",
        phone="+1234567890",
        name="Test Customer",
        default_address="123 Test St, Test City, TS 12345",
    )


@pytest.fixture
def sample_inventory_item() -> InventoryItem:
    """Create a sample inventory item."""
    return InventoryItem(
        item_id="pizza_pepperoni",
        name="Pepperoni Pizza",
        category="pizza",
        quantity=50,
        low_stock_threshold=10,
        ingredients=["dough", "sauce", "cheese", "pepperoni"],
    )


@pytest.fixture
def sample_order_item() -> OrderItem:
    """Create a sample order item."""
    from decimal import Decimal

    item = OrderItem(
        item_id="pizza_pepperoni",
        name="Pepperoni Pizza",
        quantity=2,
        unit_price=Decimal("15.99"),
        subtotal=Decimal("31.98"),
    )
    return item


@pytest.fixture
def sample_order(sample_customer: Customer, sample_order_item: OrderItem) -> Order:
    """Create a sample order."""
    order = Order(
        customer_id=sample_customer.id,
        conversation_id=uuid4(),
        delivery_address=sample_customer.default_address,
    )
    order.add_item(sample_order_item)
    return order


@pytest.fixture
def sample_driver() -> Driver:
    """Create a sample driver."""
    return Driver(
        name="Test Driver",
        status=DriverStatus.AVAILABLE,
        current_location=Location(lat=40.7128, lng=-74.0060),
        vehicle_type="car",
        rating=4.8,
    )


@pytest_asyncio.fixture
async def sample_conversation(
    conversation_manager: ConversationManager,
    sample_customer: Customer,
) -> ConversationState:
    """Create a sample conversation."""
    return await conversation_manager.create_conversation(customer_id=sample_customer.id)
