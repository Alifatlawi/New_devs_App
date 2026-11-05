"""Regression tests: tenant data must not be readable without verified credentials."""
import base64
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import dashboard, login

app = FastAPI()
app.include_router(login.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
client = TestClient(app)

SUMMARY_URL = "/api/v1/dashboard/summary?property_id=prop-001"


def _unsigned_jwt(payload: dict) -> str:
    def b64(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    return f"{b64({'alg': 'HS256', 'typ': 'JWT'})}.{b64(payload)}.not-a-real-signature"


def test_mock_token_is_rejected():
    response = client.get(SUMMARY_URL, headers={"Authorization": "Bearer mock-token-123"})
    assert response.status_code == 401


def test_forged_unsigned_jwt_is_rejected():
    token = _unsigned_jwt({"email": "candidate@propertyflow.com", "aud": "authenticated"})
    response = client.get(SUMMARY_URL, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_login_with_wrong_password_is_rejected():
    for email in ("candidate@propertyflow.com", "sunset@propertyflow.com"):
        response = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
        assert response.status_code == 401, email


def test_login_with_valid_credentials_returns_token_for_own_tenant():
    response = client.post("/api/v1/auth/login", json={"email": "ocean@propertyflow.com", "password": "client_b_2024"})
    assert response.status_code == 200
    assert response.json()["user"]["tenant_id"] == "tenant-b"
