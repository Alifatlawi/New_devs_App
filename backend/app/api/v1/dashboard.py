import logging
from typing import Any, Dict, List

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


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str = Query(..., min_length=1, max_length=64),
    tenant_id: str = Depends(require_tenant),
) -> Dict[str, Any]:
    try:
        revenue_data = await get_revenue_summary(property_id, tenant_id)
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

    total_revenue_float = float(revenue_data['total'])

    return {
        "property_id": revenue_data['property_id'],
        "total_revenue": total_revenue_float,
        "currency": revenue_data['currency'],
        "reservations_count": revenue_data['count']
    }
