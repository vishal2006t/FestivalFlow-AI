"""Audit and Integration Verification Test Suite for FestivalFlow AI.

Covers:
1. Bus Driver dashboard icon verification (InfoIcon defined & imported).
2. Authentication & Role-Based Access Control (Admin vs Driver).
3. Operations Report generation and fallback retrieval.
4. Assignments and schedules retrieval and driver status updates.
5. Fleet tracking and telematics for the fixed 17-bus fleet.
6. Empty data and error handling.
7. Database conservation and record preservation.
"""

import os
import re
import pytest
from fastapi.testclient import TestClient
from main import app
from app.database import get_db_connection

client = TestClient(app)


# ==================== Helpers ====================

def get_admin_token() -> str:
    res = client.post("/api/auth/login", json={
        "username": "admin_chennai",
        "password": "Admin@Depot2026",
        "role": "depot_admin"
    })
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    return res.json()["token"]


def get_driver_token() -> str:
    res = client.post("/api/auth/login", json={
        "username": "driver_ramesh",
        "password": "Driver@2026",
        "role": "driver"
    })
    assert res.status_code == 200, f"Driver login failed: {res.text}"
    return res.json()["token"]


# ==================== Task 1: Icon & White Screen Fix ====================

def test_bus_driver_dashboard_info_icon_defined():
    """Verify that InfoIcon is exported by Icons.jsx and imported by BusDriverDashboard.jsx."""
    icons_path = "frontend/src/components/Icons.jsx"
    dashboard_path = "frontend/src/components/BusDriverDashboard.jsx"

    assert os.path.exists(icons_path), "Icons.jsx missing!"
    assert os.path.exists(dashboard_path), "BusDriverDashboard.jsx missing!"

    with open(icons_path, "r", encoding="utf-8") as f:
        icons_code = f.read()
    with open(dashboard_path, "r", encoding="utf-8") as f:
        dashboard_code = f.read()

    # Check export in Icons.jsx
    assert "export const InfoIcon" in icons_code, "InfoIcon not exported in Icons.jsx"

    # Check import in BusDriverDashboard.jsx
    import_match = re.search(r"import\s+\{([^}]+)\}\s+from\s+['\"]\./Icons['\"]", dashboard_code)
    assert import_match is not None, "Could not find ./Icons import in BusDriverDashboard.jsx"
    assert "InfoIcon" in import_match.group(1), "InfoIcon is missing from imports in BusDriverDashboard.jsx"

    # Ensure no unresolved InfoIcon references exist in JSX
    assert "<InfoIcon" in dashboard_code, "InfoIcon should be used in JSX"


# ==================== Task 2: Authentication & RBAC ====================

def test_admin_and_driver_login():
    """Verify both Depot Admin and Bus Driver authenticate with valid credentials."""
    admin_token = get_admin_token()
    driver_token = get_driver_token()
    assert admin_token is not None and len(admin_token) > 20
    assert driver_token is not None and len(driver_token) > 20


def test_rbac_access_control():
    """Verify role-based authorization: Driver cannot access Admin endpoints."""
    driver_token = get_driver_token()

    # Driver blocked from Admin summary
    res_summary = client.get("/api/admin/summary", headers={"Authorization": f"Bearer {driver_token}"})
    assert res_summary.status_code in [401, 403]

    # Driver blocked from creating dispatch plans
    res_plan = client.post("/api/dispatch/plan", json={}, headers={"Authorization": f"Bearer {driver_token}"})
    assert res_plan.status_code in [401, 403]

    # Unauthenticated blocked
    res_unauth = client.get("/api/admin/summary")
    assert res_unauth.status_code in [401, 403]


# ==================== Task 3: Operations Report ====================

def test_operations_report_endpoints():
    """Verify Operations Report retrieval and generation."""
    admin_token = get_admin_token()

    # 1. Test GET /api/operations-report
    get_res = client.get("/api/operations-report", headers={"Authorization": f"Bearer {admin_token}"})
    assert get_res.status_code == 200, f"GET /api/operations-report failed: {get_res.text}"
    report_data = get_res.json()
    assert "overall_status" in report_data
    assert "passenger_demand" in report_data
    assert "bus_allocation_recommendation" in report_data

    # 2. Test POST /api/operations-report/generate
    gen_res = client.post("/api/operations-report/generate", headers={"Authorization": f"Bearer {admin_token}"})
    assert gen_res.status_code == 200, f"POST /api/operations-report/generate failed: {gen_res.text}"
    fresh_data = gen_res.json()
    assert fresh_data["overall_status"]["total_buses"] == 17

    # 3. Test active fallback endpoints
    overview_res = client.get("/api/reallocation-overview", headers={"Authorization": f"Bearer {admin_token}"})
    assert overview_res.status_code == 200
    assert overview_res.json()["is_fleet_conserved"] is True


# ==================== Task 4: Assignments & Schedules ====================

def test_assignments_and_schedules_endpoints():
    """Verify assignment listing and driver schedule status updates."""
    admin_token = get_admin_token()
    driver_token = get_driver_token()

    # 1. Test GET /api/assignments
    asgn_res = client.get("/api/assignments", headers={"Authorization": f"Bearer {admin_token}"})
    assert asgn_res.status_code == 200
    assignments = asgn_res.json()
    assert isinstance(assignments, list)

    # 2. Test GET /api/schedules
    sched_res = client.get("/api/schedules", headers={"Authorization": f"Bearer {admin_token}"})
    assert sched_res.status_code == 200
    schedules = sched_res.json()
    assert len(schedules) > 0

    # 3. Test status update on schedule #1 with valid enum status (Departed)
    sched_id = schedules[0]["id"]
    patch_res = client.patch(
        f"/api/schedules/{sched_id}/status",
        json={"status": "Departed"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "Departed"


# ==================== Task 5: Live Tracking ====================

def test_tracking_live_positions_endpoints():
    """Verify live telematics positions and simulated fleet tracking."""
    admin_token = get_admin_token()

    # 1. Test GET /api/tracking/live-positions
    track_res = client.get("/api/tracking/live-positions", headers={"Authorization": f"Bearer {admin_token}"})
    assert track_res.status_code == 200
    track_data = track_res.json()
    assert track_data["status"] == "SIMULATED_GPS_ACTIVE"
    assert "SIMULATED" in track_data["data_notice"]
    assert track_data["total_tracked_buses"] == 17
    assert len(track_data["buses"]) == 17

    # 2. Test active /api/buses/telematics
    tel_res = client.get("/api/buses/telematics", headers={"Authorization": f"Bearer {admin_token}"})
    assert tel_res.status_code == 200
    buses = tel_res.json()
    assert len(buses) == 17


# ==================== Task 6: Error Handling & Data Conservation ====================

def test_empty_data_and_error_handling():
    """Verify error handling on invalid requests without application crash."""
    admin_token = get_admin_token()

    # Invalid JSON payload
    bad_res = client.post(
        "/api/dispatch/plan",
        json={"invalid_key": 99999},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert bad_res.status_code == 422 # Validation error handled cleanly

    # Invalid schedule ID
    not_found_res = client.get(
        "/api/schedules/999999",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert not_found_res.status_code == 404


def test_database_records_preserved():
    """Verify primary database tables and fixed fleet of 17 buses are strictly conserved."""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM buses")
    assert cur.fetchone()[0] == 17, "Fixed fleet constraint violated!"

    cur.execute("SELECT COUNT(*) FROM users")
    assert cur.fetchone()[0] == 5, "Users modified or deleted!"

    conn.close()
