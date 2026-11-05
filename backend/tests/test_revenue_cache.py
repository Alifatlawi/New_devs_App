import asyncio
from typing import Any, Dict, List, Optional, Tuple

from redis.exceptions import ConnectionError as RedisConnectionError

from app.services import cache

TOTALS = {"tenant-a": "2250.00", "tenant-b": "0.00"}


class FakeRedis:
    def __init__(self) -> None:
        self.store: Dict[str, bytes] = {}

    async def get(self, key: str) -> Optional[bytes]:
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value.encode()


class DownRedis:
    async def get(self, key: str) -> Optional[bytes]:
        raise RedisConnectionError("redis is down")

    async def setex(self, key: str, ttl: int, value: str) -> None:
        raise RedisConnectionError("redis is down")


def install_fake_calculator(monkeypatch) -> List[Tuple[Any, ...]]:
    calls: List[Tuple[Any, ...]] = []

    async def fake_calculate(property_id: str, tenant_id: str, year=None, month=None) -> Dict[str, Any]:
        calls.append((tenant_id, property_id, year, month))
        return {"property_id": property_id, "tenant_id": tenant_id, "total": TOTALS[tenant_id], "currency": "USD", "count": 0}

    monkeypatch.setattr(cache, "calculate_revenue", fake_calculate)
    return calls


def test_same_property_id_in_two_tenants_never_shares_a_cache_entry(monkeypatch):
    monkeypatch.setattr(cache, "redis_client", FakeRedis())
    calls = install_fake_calculator(monkeypatch)

    sunset = asyncio.run(cache.get_revenue_summary("prop-001", "tenant-a"))
    ocean = asyncio.run(cache.get_revenue_summary("prop-001", "tenant-b"))

    assert sunset["total"] == "2250.00"
    assert ocean["total"] == "0.00"
    assert [c[0] for c in calls] == ["tenant-a", "tenant-b"]  # tenant-b was not served tenant-a's entry


def test_repeat_read_is_served_from_cache(monkeypatch):
    monkeypatch.setattr(cache, "redis_client", FakeRedis())
    calls = install_fake_calculator(monkeypatch)

    first = asyncio.run(cache.get_revenue_summary("prop-001", "tenant-a", 2024, 3))
    second = asyncio.run(cache.get_revenue_summary("prop-001", "tenant-a", 2024, 3))

    assert first == second
    assert len(calls) == 1


def test_cache_key_contains_tenant_property_and_period():
    assert cache.revenue_cache_key("tenant-a", "prop-001") == "revenue:tenant-a:prop-001:all"
    assert cache.revenue_cache_key("tenant-b", "prop-001", 2024, 3) == "revenue:tenant-b:prop-001:2024-03"


def test_redis_outage_falls_back_to_the_database(monkeypatch):
    monkeypatch.setattr(cache, "redis_client", DownRedis())
    install_fake_calculator(monkeypatch)

    result = asyncio.run(cache.get_revenue_summary("prop-001", "tenant-a"))

    assert result["total"] == "2250.00"
