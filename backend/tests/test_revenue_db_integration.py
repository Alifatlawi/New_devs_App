"""Runs against the seeded Postgres from docker-compose; skipped when no database is reachable."""
import asyncio
from typing import Any, Dict

import pytest
from sqlalchemy import text

from app.core.database_pool import db_pool
from app.services.reservations import PropertyNotFoundError, calculate_revenue, list_properties


async def _database_reachable() -> bool:
    try:
        async with db_pool.get_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except OSError:
        return False
    finally:
        await db_pool.close()


async def _collect() -> Dict[str, Any]:
    try:
        results = {
            "sunset_properties": await list_properties("tenant-a"),
            "ocean_properties": await list_properties("tenant-b"),
            "sunset_beach_march": await calculate_revenue("prop-001", "tenant-a", 2024, 3),
            "sunset_beach_feb": await calculate_revenue("prop-001", "tenant-a", 2024, 2),
            "ocean_prop_001": await calculate_revenue("prop-001", "tenant-b"),
        }
        try:
            await calculate_revenue("prop-002", "tenant-b")
            results["ocean_reads_sunset_property"] = "allowed"
        except PropertyNotFoundError:
            results["ocean_reads_sunset_property"] = "not found"
        return results
    finally:
        await db_pool.close()  # engine is bound to this event loop


def test_seed_data_totals_are_tenant_isolated_and_timezone_correct():
    # Skip only when there is no database at all; any SQL error must fail the test.
    if not asyncio.run(_database_reachable()):
        pytest.skip("database not reachable")
    results = asyncio.run(_collect())

    # res-tz-1 (2024-02-29 23:30Z) is 1 March in Paris, so March has 4 bookings, February none.
    assert (results["sunset_beach_march"]["total"], results["sunset_beach_march"]["count"]) == ("2250.00", 4)
    assert (results["sunset_beach_feb"]["total"], results["sunset_beach_feb"]["count"]) == ("0.00", 0)
    # Ocean's own prop-001 (Mountain Lodge Beta) has no bookings; it must not see Sunset's prop-001.
    assert (results["ocean_prop_001"]["total"], results["ocean_prop_001"]["count"]) == ("0.00", 0)
    assert results["ocean_reads_sunset_property"] == "not found"
    # Property lists are tenant-scoped: prop-001 is a different property for each tenant.
    sunset = {p["id"]: p for p in results["sunset_properties"]}
    ocean = {p["id"]: p for p in results["ocean_properties"]}
    assert set(sunset) == {"prop-001", "prop-002", "prop-003"}
    assert set(ocean) == {"prop-001", "prop-004", "prop-005"}
    assert (sunset["prop-001"]["name"], sunset["prop-001"]["latest_booking_year"]) == ("Beach House Alpha", 2024)
    assert (ocean["prop-001"]["name"], ocean["prop-001"]["latest_booking_year"]) == ("Mountain Lodge Beta", None)
