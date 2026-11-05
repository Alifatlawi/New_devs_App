import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.core.auth import authenticate_request as get_current_user
from app.models.auth import AuthenticatedUser
from app.services.cache import get_revenue_summary
from app.services.reservations import MixedCurrencyError, PropertyNotFoundError, list_properties

logger = logging.getLogger(__name__)

router = APIRouter()

DATA_UNAVAILABLE = "Revenue data is temporarily unavailable"


class RevenueSummaryResponse(BaseModel):
    property_id: str
    # Decimal string rounded to cents (e.g. "2250.00"); never a float, so no binary rounding error.
    total_revenue: str
    currency: str
    reservations_count: int
    year: Optional[int] = None
    month: Optional[int] = None


class PropertyResponse(BaseModel):
    id: str
    name: str
    timezone: str


def require_tenant(current_user: AuthenticatedUser = Depends(get_current_user)) -> str:
    """Fail closed: a user without a resolved tenant must never fall back to a shared/default tenant."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenant is associated with this account")
    return current_user.tenant_id


@router.get("/dashboard/properties", response_model=List[PropertyResponse])
async def get_dashboard_properties(tenant_id: str = Depends(require_tenant)) -> List[Dict[str, Any]]:
    try:
        return await list_properties(tenant_id)
    except (SQLAlchemyError, OSError):
        logger.exception("Failed to list properties for tenant %s", tenant_id)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=DATA_UNAVAILABLE)


@router.get("/dashboard/summary", response_model=RevenueSummaryResponse)
async def get_dashboard_summary(
    property_id: str = Query(..., min_length=1, max_length=64),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12, description="Calendar month in the property's local time zone"),
    tenant_id: str = Depends(require_tenant),
) -> RevenueSummaryResponse:
    if (year is None) != (month is None):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provide both year and month, or neither")

    try:
        revenue_data = await get_revenue_summary(property_id, tenant_id, year, month)
    except PropertyNotFoundError:
        # Same 404 whether the property doesn't exist or belongs to another tenant (no enumeration).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    except MixedCurrencyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reservations use more than one currency and cannot be summed into one total",
        )
    except (SQLAlchemyError, OSError):
        logger.exception("Revenue query failed for tenant %s property %s", tenant_id, property_id)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=DATA_UNAVAILABLE)

    return RevenueSummaryResponse(
        property_id=revenue_data["property_id"],
        total_revenue=revenue_data["total"],
        currency=revenue_data["currency"],
        reservations_count=revenue_data["count"],
        year=year,
        month=month,
    )
