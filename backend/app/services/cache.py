import json
import logging
import os
from typing import Any, Dict, Optional

import redis.asyncio as redis
from redis.exceptions import RedisError

from app.services.reservations import calculate_revenue

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 300

# Initialize Redis client (typically configured centrally).
redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


def revenue_cache_key(tenant_id: str, property_id: str, year: Optional[int] = None, month: Optional[int] = None) -> str:
    # Property IDs are only unique within a tenant (PK is (id, tenant_id)), so the tenant
    # must be part of the key or tenants sharing an ID like "prop-001" see each other's data.
    period = f"{year:04d}-{month:02d}" if year is not None and month is not None else "all"
    return f"revenue:{tenant_id}:{property_id}:{period}"


async def get_revenue_summary(
    property_id: str,
    tenant_id: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Fetches revenue summary, utilizing caching to improve performance.
    A Redis outage degrades to an uncached read instead of failing the request.
    """
    cache_key = revenue_cache_key(tenant_id, property_id, year, month)

    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except (RedisError, ValueError) as exc:  # ValueError: corrupt/non-JSON entry -> recompute
        logger.warning("Revenue cache read failed for %s: %s", cache_key, exc)

    result = await calculate_revenue(property_id, tenant_id, year, month)

    try:
        await redis_client.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(result))
    except RedisError as exc:
        logger.warning("Revenue cache write failed for %s: %s", cache_key, exc)

    return result
