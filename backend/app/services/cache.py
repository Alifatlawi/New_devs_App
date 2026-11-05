import json
import logging
import os
from typing import Any, Dict

import redis.asyncio as redis
from redis.exceptions import RedisError

from app.services.reservations import calculate_total_revenue

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 300

# Initialize Redis client (typically configured centrally).
redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


def revenue_cache_key(tenant_id: str, property_id: str) -> str:
    # Property IDs are only unique within a tenant (PK is (id, tenant_id)), so the tenant
    # must be part of the key or tenants sharing an ID like "prop-001" see each other's data.
    return f"revenue:{tenant_id}:{property_id}"


async def get_revenue_summary(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Fetches revenue summary, utilizing caching to improve performance.
    A Redis outage degrades to an uncached read instead of failing the request.
    """
    cache_key = revenue_cache_key(tenant_id, property_id)

    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except RedisError as exc:
        logger.warning("Revenue cache read failed for %s: %s", cache_key, exc)

    result = await calculate_total_revenue(property_id, tenant_id)

    try:
        await redis_client.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(result))
    except RedisError as exc:
        logger.warning("Revenue cache write failed for %s: %s", cache_key, exc)

    return result
