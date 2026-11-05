import logging
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database_pool import db_pool

logger = logging.getLogger(__name__)

DEFAULT_CURRENCY = "USD"
CENT = Decimal("0.01")


class PropertyNotFoundError(Exception):
    """The property does not exist for this tenant (also raised when it belongs to another tenant)."""


class MixedCurrencyError(Exception):
    """Reservations in different currencies cannot be summed into one total."""


def to_money(amount: Decimal) -> Decimal:
    """
    Round a summed amount to cents, once, at the end.

    Amounts are stored as NUMERIC(10,3) (sub-cent precision), so we sum the exact values
    in Postgres and round half-up only the final total. Rounding each booking first, or
    going through float, is what made totals drift by a cent here and there.
    """
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def month_bounds_utc(year: int, month: int, tz_name: str) -> Tuple[datetime, datetime]:
    """
    [start, end) of a calendar month in the property's local time zone, as UTC instants.

    zoneinfo applies the correct UTC offset for each date, so DST changes inside the month
    are handled (e.g. Paris March 2024 starts at 23:00Z on 29 Feb and ends at 22:00Z on 31 Mar).
    """
    tz = ZoneInfo(tz_name)
    start = datetime(year, month, 1, tzinfo=tz)
    end = datetime(year + 1, 1, 1, tzinfo=tz) if month == 12 else datetime(year, month + 1, 1, tzinfo=tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


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


async def calculate_revenue(
    property_id: str,
    tenant_id: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Aggregates revenue for one property of one tenant: all time, or for one calendar month.

    A reservation counts towards the month of its check-in date in the property's local
    time zone (a 23:30 UTC check-in on 29 Feb is 1 March in Paris).

    Raises PropertyNotFoundError if the property is not the tenant's, and lets database
    errors propagate so the API can report them instead of serving made-up numbers.
    """
    async with db_pool.get_session() as session:
        prop = await _get_property(session, property_id, tenant_id)

        params: Dict[str, Any] = {"property_id": property_id, "tenant_id": tenant_id}
        period_filter = ""
        if year is not None and month is not None:
            params["start"], params["end"] = month_bounds_utc(year, month, prop["timezone"])
            # Constant SQL fragment; the values are still bound parameters. Half-open
            # [start, end) so a check-in exactly at local midnight on the 1st counts once.
            period_filter = "AND check_in_date >= :start AND check_in_date < :end"

        result = await session.execute(
            text(f"""
                SELECT currency, SUM(total_amount) AS total, COUNT(*) AS reservation_count
                FROM reservations
                WHERE property_id = :property_id AND tenant_id = :tenant_id {period_filter}
                GROUP BY currency
            """),
            params,
        )
        rows = result.mappings().all()

    if len(rows) > 1:
        raise MixedCurrencyError(property_id)

    total = Decimal(rows[0]["total"]) if rows else Decimal("0")
    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "total": str(to_money(total)),
        "currency": (rows[0]["currency"] if rows else None) or DEFAULT_CURRENCY,
        "count": rows[0]["reservation_count"] if rows else 0,
    }
