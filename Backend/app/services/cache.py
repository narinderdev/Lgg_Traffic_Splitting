from __future__ import annotations

import json
from collections.abc import AsyncIterator

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

settings = get_settings()

_redis_client: Redis | None = None


def get_redis() -> Redis | None:
    global _redis_client
    if not settings.redis_url:
        return None
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def get_cache_value(key: str) -> dict | list | None:
    client = get_redis()
    if client is None:
        return None
    try:
        payload = await client.get(key)
    except RedisError:
        return None
    return json.loads(payload) if payload else None


async def set_cache_value(key: str, value: dict | list) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        await client.set(key, json.dumps(value, default=str), ex=settings.stats_cache_ttl_seconds)
    except RedisError:
        return


async def invalidate_experiment_cache(experiment_id: str) -> None:
    client = get_redis()
    if client is None:
        return
    pattern = f"experiment-stats:{experiment_id}:*"
    try:
        async for key in client.scan_iter(match=pattern):
            await client.delete(key)
    except RedisError:
        return
