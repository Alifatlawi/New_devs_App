"""Runs against the seeded Postgres from docker-compose; skipped when no database is reachable."""
import asyncio
from typing import Any, Dict

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.database_pool import db_pool
from app.services.reservations import PropertyNotFoundError, calculate_revenue


async def _collect() -> Dict[str, Any]:
    try:
        results = {
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
    try:
        results = asyncio.run(_collect())
    except (SQLAlchemyError, OSError) as exc:
        pytest.skip(f"database not reachable: {exc}")

    # res-tz-1 (2024-02-29 23:30Z) is 1 March in Paris, so March has 4 bookings, February none.
    assert (results["sunset_beach_march"]["total"], results["sunset_beach_march"]["count"]) == ("2250.00", 4)
    assert (results["sunset_beach_feb"]["total"], results["sunset_beach_feb"]["count"]) == ("0.00", 0)
    # Ocean's own prop-001 (Mountain Lodge Beta) has no bookings; it must not see Sunset's prop-001.
    assert (results["ocean_prop_001"]["total"], results["ocean_prop_001"]["count"]) == ("0.00", 0)
    assert results["ocean_reads_sunset_property"] == "not found"
