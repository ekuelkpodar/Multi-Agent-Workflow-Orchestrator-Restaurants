"""Reset all state in Redis (useful for testing)."""

import asyncio

from src.state.manager import StateManager


async def reset_all_state() -> None:
    """Clear all data from Redis."""
    print("\n⚠️  WARNING: This will delete ALL data from Redis!")
    response = input("Are you sure? (yes/no): ")

    if response.lower() != "yes":
        print("Cancelled.")
        return

    print("\nResetting state...")

    state_manager = StateManager()
    await state_manager.connect()

    # In production, use SCAN to avoid blocking
    # For demo, we'll use FLUSHDB
    if state_manager.redis_client:
        await state_manager.redis_client.flushdb()

    await state_manager.disconnect()

    print("✓ All state cleared from Redis\n")


if __name__ == "__main__":
    asyncio.run(reset_all_state())
