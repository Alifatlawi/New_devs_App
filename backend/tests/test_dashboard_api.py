from typing import Any, Dict, List, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.v1 import dashboard
from app.core.auth import authenticate_request
from app.models.auth import AuthenticatedUser
from app.services.reservations import PropertyNotFoundError

SUMMARY_URL = "/api/v1/dashboard/summary"


def make_client(tenant_id: Optional[str]) -> TestClient:
    app = FastAPI()
    app.include_router(dashboard.router, prefix="/api/v1")
    app.dependency_overrides[authenticate_request] = lambda: AuthenticatedUser(
        id="user-1", email="user@example.com", permissions=[], cities=[], is_admin=False, tenant_id=tenant_id
    )
    return TestClient(app)


@pytest.fixture
def summary_calls(monkeypatch) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []

    async def fake_summary(property_id: str, tenant_id: str, year=None, month=None) -> Dict[str, Any]:
        calls.append({"property_id": property_id, "tenant_id": tenant_id, "year": year, "month": month})
        if tenant_id != "tenant-a":
            raise PropertyNotFoundError(property_id)
        return {"property_id": property_id, "tenant_id": tenant_id, "total": "2250.00", "currency": "USD", "count": 4}

    monkeypatch.setattr(dashboard, "get_revenue_summary", fake_summary)
    return calls


def test_summary_uses_tenant_from_token_and_returns_money_as_string(summary_calls):
    response = make_client("tenant-a").get(SUMMARY_URL, params={"property_id": "prop-001", "year": 2024, "month": 3})

    assert response.status_code == 200
    assert response.json() == {
        "property_id": "prop-001",
        "total_revenue": "2250.00",
        "currency": "USD",
        "reservations_count": 4,
        "year": 2024,
        "month": 3,
    }
    assert summary_calls == [{"property_id": "prop-001", "tenant_id": "tenant-a", "year": 2024, "month": 3}]


def test_property_of_another_tenant_is_not_found(summary_calls):
    response = make_client("tenant-b").get(SUMMARY_URL, params={"property_id": "prop-002"})

    assert response.status_code == 404


def test_user_without_tenant_is_rejected_not_defaulted(summary_calls):
    response = make_client(None).get(SUMMARY_URL, params={"property_id": "prop-001"})

    assert response.status_code == 403
    assert summary_calls == []


@pytest.mark.parametrize("params", [{"year": 2024}, {"month": 3}, {"year": 2024, "month": 13}])
def test_invalid_period_is_rejected(summary_calls, params):
    response = make_client("tenant-a").get(SUMMARY_URL, params={"property_id": "prop-001", **params})

    assert response.status_code == 422
    assert summary_calls == []


def test_database_outage_returns_503_instead_of_mock_numbers(monkeypatch):
    async def failing_summary(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        raise OperationalError("SELECT 1", {}, ConnectionRefusedError("db down"))

    monkeypatch.setattr(dashboard, "get_revenue_summary", failing_summary)

    response = make_client("tenant-a").get(SUMMARY_URL, params={"property_id": "prop-001"})

    assert response.status_code == 503
