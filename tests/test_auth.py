"""Tests for two-role authentication, password verification, and authorization enforcement."""

import pytest
from fastapi.testclient import TestClient
from main import app
from app.database import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure a fresh database before each test suite execution."""
    init_db(force_reset=True)


def test_admin_login_success():
    """Bus Depot Admin logs in with valid credentials."""
    response = client.post("/api/auth/login", json={
        "username": "admin_chennai",
        "password": "Admin@Depot2026",
        "role": "depot_admin"
    })
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["user"]["username"] == "admin_chennai"
    assert data["user"]["role"] == "depot_admin"


def test_driver_login_success():
    """Bus Driver logs in with valid credentials."""
    response = client.post("/api/auth/login", json={
        "username": "driver_ramesh",
        "password": "Driver@2026",
        "role": "driver"
    })
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["user"]["username"] == "driver_ramesh"
    assert data["user"]["role"] == "driver"


def test_login_invalid_password():
    """Login fails when incorrect password is provided."""
    response = client.post("/api/auth/login", json={
        "username": "admin_chennai",
        "password": "WrongPassword123",
        "role": "depot_admin"
    })
    assert response.status_code == 401
    assert "Invalid username or password" in response.json()["detail"]


def test_login_nonexistent_user():
    """Login fails when username does not exist."""
    response = client.post("/api/auth/login", json={
        "username": "non_existent_user",
        "password": "AnyPassword",
        "role": "depot_admin"
    })
    assert response.status_code == 401
    assert "Invalid username or password" in response.json()["detail"]


def test_login_role_mismatch():
    """Login fails when a driver tries to log in as depot admin."""
    response = client.post("/api/auth/login", json={
        "username": "driver_ramesh",
        "password": "Driver@2026",
        "role": "depot_admin"
    })
    assert response.status_code == 401
    assert "Invalid credentials for selected role" in response.json()["detail"]


def test_protected_endpoint_without_token():
    """Accessing protected endpoint without Bearer token returns 401."""
    response = client.get("/api/schedules")
    assert response.status_code == 401


def test_protected_endpoint_with_invalid_token():
    """Accessing protected endpoint with an invalid token returns 401."""
    response = client.get("/api/schedules", headers={"Authorization": "Bearer invalid_token_12345"})
    assert response.status_code == 401


def test_driver_forbidden_from_admin_endpoint():
    """Bus Driver cannot access Depot Admin schedule management endpoint (403 Forbidden)."""
    # 1. Login as driver
    login_res = client.post("/api/auth/login", json={
        "username": "driver_ramesh",
        "password": "Driver@2026",
        "role": "driver"
    })
    driver_token = login_res.json()["token"]

    # 2. Driver attempts to access Admin endpoint
    response = client.get("/api/schedules", headers={"Authorization": f"Bearer {driver_token}"})
    assert response.status_code == 403
    assert "Bus Depot Admin privileges required" in response.json()["detail"]


def test_admin_forbidden_from_driver_endpoint():
    """Bus Depot Admin cannot access Driver-only assigned schedule endpoint (403 Forbidden)."""
    # 1. Login as admin
    login_res = client.post("/api/auth/login", json={
        "username": "admin_chennai",
        "password": "Admin@Depot2026",
        "role": "depot_admin"
    })
    admin_token = login_res.json()["token"]

    # 2. Admin attempts to access Driver endpoint
    response = client.get("/api/driver/my-schedules", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 403
    assert "Bus Driver privileges required" in response.json()["detail"]


def test_logout_invalidates_token():
    """Logging out invalidates the session token."""
    login_res = client.post("/api/auth/login", json={
        "username": "admin_chennai",
        "password": "Admin@Depot2026",
        "role": "depot_admin"
    })
    token = login_res.json()["token"]

    # Verify token works
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200

    # Logout
    logout_res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200

    # Subsequent access fails
    me_res_after = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res_after.status_code == 401


def test_demo_accounts_endpoint():
    """Demo accounts endpoint returns documented demo logins."""
    response = client.get("/api/auth/demo-accounts")
    assert response.status_code == 200
    data = response.json()
    assert "depot_admins" in data
    assert "bus_drivers" in data
    assert len(data["depot_admins"]) >= 2
    assert len(data["bus_drivers"]) >= 3
