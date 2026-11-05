import logging
from decimal import Decimal
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database_pool import db_pool

logger = logging.getLogger(__name__)

DEFAULT_CURRENCY = "USD"


class PropertyNotFoundError(Exception):
    """The property does not exist for this tenant (also raised when it belongs to another tenant)."""


class MixedCurrencyError(Exception):
    """Reservations in different currencies cannot be summed into one total."""


async def _get_property(session: AsyncSession, property_id: str, tenant_id: str) -> Dict[str, Any]:
    result = await session.execute(
        text("SELECT id, name, timezone FROM properties WHERE id = :property_id AND tenant_id = :tenant_id"),
        {"property_id": property_id, "tenant_id": tenant_id},
    )
    row = result.mappings().first()
    if row is None:
        raise PropertyNotFoundError(property_id)
    return dict(row)


async def list_properties(tenant_id: str) -> List[Dict[str, Any]]:
    """Properties owned by one tenant only."""
    async with db_pool.get_session() as session:
        result = await session.execute(
            text("SELECT id, name, timezone FROM properties WHERE tenant_id = :tenant_id ORDER BY name"),
            {"tenant_id": tenant_id},
        )
        return [dict(row) for row in result.mappings().all()]


async def calculate_total_revenue(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Aggregates revenue for one property of one tenant.

    Raises PropertyNotFoundError if the property is not the tenant's, and lets database
    errors propagate so the API can report them instead of serving made-up numbers.
    """
    async with db_pool.get_session() as session:
        await _get_property(session, property_id, tenant_id)

        result = await session.execute(
            text("""
                SELECT currency, SUM(total_amount) AS total, COUNT(*) AS reservation_count
                FROM reservations
                WHERE property_id = :property_id AND tenant_id = :tenant_id
                GROUP BY currency
            """),
            {"property_id": property_id, "tenant_id": tenant_id},
        )
        rows = result.mappings().all()

    if len(rows) > 1:
        raise MixedCurrencyError(property_id)

    total = Decimal(rows[0]["total"]) if rows else Decimal("0")
    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "total": str(total),
        "currency": (rows[0]["currency"] if rows else None) or DEFAULT_CURRENCY,
        "count": rows[0]["reservation_count"] if rows else 0,
    }
