"""Redis-based state manager for shared state across agents."""

import json
from typing import Any
from uuid import UUID

import redis.asyncio as redis

from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class StateManager:
    """Centralized state management using Redis."""

    def __init__(self) -> None:
        settings = get_settings()
        self.redis_client: redis.Redis | None = None
        self.redis_url = settings.redis_url

    async def connect(self) -> None:
        """Establish Redis connection."""
        if self.redis_client is None:
            self.redis_client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("redis_connected", url=self.redis_url)

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            logger.info("redis_disconnected")

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """Set a value in Redis with optional TTL."""
        if not self.redis_client:
            await self.connect()

        # Serialize complex objects to JSON
        if isinstance(value, (dict, list)):
            value = json.dumps(value)

        await self.redis_client.set(key, value)

        if ttl:
            await self.redis_client.expire(key, ttl)

        logger.debug("state_set", key=key, ttl=ttl)

    async def get(self, key: str) -> Any:
        """Get a value from Redis."""
        if not self.redis_client:
            await self.connect()

        value = await self.redis_client.get(key)

        if value:
            # Try to deserialize JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value

        return None

    async def delete(self, key: str) -> None:
        """Delete a key from Redis."""
        if not self.redis_client:
            await self.connect()

        await self.redis_client.delete(key)
        logger.debug("state_deleted", key=key)

    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        if not self.redis_client:
            await self.connect()

        return bool(await self.redis_client.exists(key))

    async def hset(self, key: str, field: str, value: Any) -> None:
        """Set a hash field."""
        if not self.redis_client:
            await self.connect()

        if isinstance(value, (dict, list)):
            value = json.dumps(value)

        await self.redis_client.hset(key, field, value)

    async def hget(self, key: str, field: str) -> Any:
        """Get a hash field."""
        if not self.redis_client:
            await self.connect()

        value = await self.redis_client.hget(key, field)

        if value:
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value

        return None

    async def hgetall(self, key: str) -> dict[str, Any]:
        """Get all hash fields."""
        if not self.redis_client:
            await self.connect()

        data = await self.redis_client.hgetall(key)

        # Try to deserialize JSON values
        result = {}
        for field, value in data.items():
            try:
                result[field] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                result[field] = value

        return result

    async def zadd(
        self,
        key: str,
        mapping: dict[str, float],
    ) -> None:
        """Add members to a sorted set."""
        if not self.redis_client:
            await self.connect()

        await self.redis_client.zadd(key, mapping)

    async def zrange(
        self,
        key: str,
        start: int = 0,
        end: int = -1,
        withscores: bool = False,
    ) -> list[Any]:
        """Get members from a sorted set."""
        if not self.redis_client:
            await self.connect()

        return await self.redis_client.zrange(key, start, end, withscores=withscores)

    async def zrem(self, key: str, *members: str) -> None:
        """Remove members from a sorted set."""
        if not self.redis_client:
            await self.connect()

        await self.redis_client.zrem(key, *members)

    async def publish(self, channel: str, message: str) -> None:
        """Publish a message to a channel."""
        if not self.redis_client:
            await self.connect()

        await self.redis_client.publish(channel, message)
        logger.debug("message_published", channel=channel)

    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter."""
        if not self.redis_client:
            await self.connect()

        return await self.redis_client.incrby(key, amount)

    async def decrement(self, key: str, amount: int = 1) -> int:
        """Decrement a counter."""
        if not self.redis_client:
            await self.connect()

        return await self.redis_client.decrby(key, amount)


# Global state manager instance
_state_manager: StateManager | None = None


async def get_state_manager() -> StateManager:
    """Get the global state manager instance."""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
        await _state_manager.connect()
    return _state_manager
