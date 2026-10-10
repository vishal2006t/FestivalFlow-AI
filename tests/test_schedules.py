"""Tests for Depot Admin schedule management, bus assignment conflict prevention, and driver dashboards."""

import pytest
from fastapi.testclient import TestClient
from main import app
from app.database import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Reset to a clean database state before each test."""
    init_db(force_reset=True)


def get_admin_token() -> str:
    """Helper to obtain a Depot Admin auth token."""
    res = client.post("/api/auth/login", json={
        "username": "admin_chennai",
        "password": "Admin@Depot2026",
        "role": "depot_admin"
    })
    return res.json()["token"]


def get_driver_token(username: str = "driver_ramesh") -> str:
    """Helper to obtain a Bus Driver auth token."""
    res = client.post("/api/auth/login", json={
        "username": username,
        "password": "Driver@2026",
        "role": "driver"
    })
    return res.json()["token"]


# ==================== Admin Schedule Management ====================

def test_admin_can_create_valid_schedule():
    """Depot Admin can successfully create a new manual schedule."""
    token = get_admin_token()
    payload = {
        "event_name": "Deepavali Cultural Mela",
        "event_date": "2026-10-15",
        "event_start_time": "17:00",
        "expected_crowd_departure": "2026-10-15T21:00",
        "depot_name": "Tech Park North Depot",
        "bus_number": "BUS-203",
        "bus_registration_no": "TN-02-B-2003",
        "bus_capacity": 70,
        "available_bus_count": 2,
        "source_stop": "Tech Hub North Stop",
        "destination_stop": "Main Bus Stand (Festival Arena)",
        "departure_time": "2026-10-15T20:30",
        "arrival_time": "2026-10-15T20:45",
        "route_details": "Direct Expressway Shuttle Corridor",
        "status": "Scheduled",
        "notes": "Pre-staged for early leavers."
    }
    response = client.post(
        "/api/schedules",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["bus_number"] == "BUS-203"
    assert data["event_name"] == "Deepavali Cultural Mela"
    assert data["status"] == "Scheduled"
    assert "id" in data


def test_invalid_arrival_time_before_departure_rejected():
    """Schedules with arrival earlier than departure are rejected with 422."""
    token = get_admin_token()
    payload = {
        "event_name": "Deepavali Cultural Mela",
        "event_date": "2026-10-15",
        "event_start_time": "17:00",
        "expected_crowd_departure": "2026-10-15T21:00",
        "depot_name": "Tech Park North Depot",
        "bus_number": "BUS-204",
        "source_stop": "Tech Hub North Stop",
        "destination_stop": "Main Bus Stand (Festival Arena)",
        "departure_time": "2026-10-15T20:30",
        "arrival_time": "2026-10-15T19:30",  # 1 hour BEFORE departure!
        "route_details": "Direct Corridor"
    }
    response = client.post(
        "/api/schedules",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 422
    assert "cannot be earlier than departure" in response.json()["detail"]


def test_bus_assignment_overlap_conflict_prevented():
    """Attempting to assign a bus to two overlapping schedules is blocked with 400."""
    token = get_admin_token()

    # BUS-201 already has a seeded schedule from 21:40 to 21:55 on 2026-10-10.
    # Attempt to assign BUS-201 from 21:45 to 22:15 (overlapping window)
    conflicting_payload = {
        "event_name": "Overlapping Test Run",
        "event_date": "2026-10-10",
        "event_start_time": "18:00",
        "expected_crowd_departure": "2026-10-10T22:00",
        "depot_name": "Tech Park North Depot",
        "bus_number": "BUS-201",  # Same bus!
        "source_stop": "Tech Hub North Stop",
        "destination_stop": "Main Bus Stand",
        "departure_time": "2026-10-10T21:45",
        "arrival_time": "2026-10-10T22:15",
        "route_details": "Conflicting Second Trip"
    }
    response = client.post(
        "/api/schedules",
        json=conflicting_payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 400
    assert "Bus Assignment Conflict" in response.json()["detail"]
    assert "BUS-201" in response.json()["detail"]


def test_driver_assignment_overlap_conflict_prevented():
    """Attempting to assign the same driver to two overlapping schedules is blocked with 400."""
    token = get_admin_token()

    # Driver R. Ramesh is already assigned to BUS-201 at 21:40 on 2026-10-10.
    # Attempt to assign the same driver to another bus BUS-204 at the same time:
    driver_res = client.get("/api/drivers", headers={"Authorization": f"Bearer {token}"})
    ramesh_user_id = next(d["user_id"] for d in driver_res.json() if "Ramesh" in d["driver_name"])

    conflicting_payload = {
        "event_name": "Driver Overlap Run",
        "event_date": "2026-10-10",
        "event_start_time": "18:00",
        "expected_crowd_departure": "2026-10-10T22:00",
        "depot_name": "Tech Park North Depot",
        "bus_number": "BUS-204",  # Different bus
        "driver_id": ramesh_user_id,  # Same driver!
        "source_stop": "Tech Hub North Stop",
        "destination_stop": "Main Bus Stand",
        "departure_time": "2026-10-10T21:40",
        "arrival_time": "2026-10-10T22:00",
        "route_details": "Corridor Shuttle"
    }
    response = client.post(
        "/api/schedules",
        json=conflicting_payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 400
    assert "Driver Assignment Conflict" in response.json()["detail"]


def test_fleet_capacity_bounds_enforced():
    """Available bus count cannot exceed total fleet of 17 buses."""
    token = get_admin_token()
    payload = {
        "event_name": "Mega Rally",
        "event_date": "2026-10-20",
        "event_start_time": "10:00",
        "expected_crowd_departure": "2026-10-20T14:00",
        "depot_name": "Tech Park North Depot",
        "bus_number": "BUS-203",
        "available_bus_count": 99,  # Impossible fleet count!
        "source_stop": "Tech Hub North Stop",
        "destination_stop": "Main Bus Stand",
        "departure_time": "2026-10-20T11:00",
        "route_details": "Test Route"
    }
    response = client.post(
        "/api/schedules",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 422


def test_admin_can_filter_schedules():
    """Admin can search and filter schedules by date, bus, route, and status."""
    token = get_admin_token()

    # Filter by bus
    res = client.get("/api/schedules?bus=BUS-201", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["bus_number"] == "BUS-201"

    # Filter by status
    res_ready = client.get("/api/schedules?status=Ready", headers={"Authorization": f"Bearer {token}"})
    assert res_ready.status_code == 200
    items_ready = res_ready.json()
    assert len(items_ready) == 1
    assert items_ready[0]["status"] == "Ready"


def test_admin_can_edit_and_delete_schedule():
    """Admin can update an existing schedule and cancel/delete it."""
    token = get_admin_token()

    # Get existing schedule #1
    schedules = client.get("/api/schedules", headers={"Authorization": f"Bearer {token}"}).json()
    sched_id = schedules[0]["id"]

    # Edit notes and status
    update_res = client.put(
        f"/api/schedules/{sched_id}",
        json={"notes": "Updated instructions from depot operations", "status": "Ready"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert update_res.status_code == 200
    assert update_res.json()["notes"] == "Updated instructions from depot operations"
    assert update_res.json()["status"] == "Ready"

    # Delete schedule
    del_res = client.delete(
        f"/api/schedules/{sched_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert del_res.status_code == 200

    # Verify schedule is gone
    check_res = client.get(f"/api/schedules/{sched_id}", headers={"Authorization": f"Bearer {token}"})
    assert check_res.status_code == 404


# ==================== Bus Driver Dashboard ====================

def test_driver_sees_only_assigned_schedule():
    """Bus Driver can only see their own assigned schedule."""
    ramesh_token = get_driver_token("driver_ramesh")
    res = client.get("/api/driver/my-schedules", headers={"Authorization": f"Bearer {ramesh_token}"})
    assert res.status_code == 200
    schedules = res.json()
    assert len(schedules) == 1
    assert schedules[0]["bus_number"] == "BUS-201"
    assert "Ramesh" in schedules[0]["driver_name"]


def test_unassigned_driver_sees_empty_state():
    """Driver with no assigned bus receives an empty schedule list."""
    anand_token = get_driver_token("driver_anand")
    res = client.get("/api/driver/my-schedules", headers={"Authorization": f"Bearer {anand_token}"})
    assert res.status_code == 200
    assert res.json() == []


def test_driver_can_update_permitted_status():
    """Driver can transition their assigned schedule through Ready -> Departed -> Completed."""
    ramesh_token = get_driver_token("driver_ramesh")
    schedules = client.get("/api/driver/my-schedules", headers={"Authorization": f"Bearer {ramesh_token}"}).json()
    sched_id = schedules[0]["id"]

    for new_status in ["Ready", "Departed", "Completed"]:
        update_res = client.patch(
            f"/api/driver/schedules/{sched_id}/status",
            json={"status": new_status},
            headers={"Authorization": f"Bearer {ramesh_token}"}
        )
        assert update_res.status_code == 200
        assert update_res.json()["status"] == new_status


def test_driver_cannot_set_forbidden_status():
    """Driver cannot set status to Cancelled or arbitrary values."""
    ramesh_token = get_driver_token("driver_ramesh")
    schedules = client.get("/api/driver/my-schedules", headers={"Authorization": f"Bearer {ramesh_token}"}).json()
    sched_id = schedules[0]["id"]

    update_res = client.patch(
        f"/api/driver/schedules/{sched_id}/status",
        json={"status": "Cancelled"},
        headers={"Authorization": f"Bearer {ramesh_token}"}
    )
    assert update_res.status_code == 422


def test_driver_cannot_update_another_drivers_schedule():
    """Driver cannot update a schedule assigned to someone else."""
    suresh_token = get_driver_token("driver_suresh")
    # Schedule #1 is assigned to driver_ramesh
    admin_token = get_admin_token()
    schedules = client.get("/api/schedules", headers={"Authorization": f"Bearer {admin_token}"}).json()
    ramesh_sched = next(s for s in schedules if s["bus_number"] == "BUS-201")

    # Suresh tries to update Ramesh's schedule
    update_res = client.patch(
        f"/api/driver/schedules/{ramesh_sched['id']}/status",
        json={"status": "Departed"},
        headers={"Authorization": f"Bearer {suresh_token}"}
    )
    assert update_res.status_code == 403
    assert "Forbidden" in update_res.json()["detail"]


# ==================== Reallocation Overview Integration ====================

def test_reallocation_overview_integration():
    """Integrates AI recommended reallocation with Admin confirmed manual schedules."""
    token = get_admin_token()
    res = client.get("/api/reallocation-overview", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "INTEGRATED_ANALYSIS"
    assert data["fixed_fleet_total"] == 17
    assert data["is_fleet_conserved"] is True
    assert "ai_recommendation" in data
    assert "admin_confirmed" in data
    assert "source_depot_impact" in data

    # AI recommends 3 buses (holding back 1 bus as commuter peak buffer)
    assert data["ai_recommendation"]["recommended_buses_to_move"] == 3
    # Admin has confirmed 2 schedules initially
    assert data["admin_confirmed"]["confirmed_schedules_count"] == 2
    # Source depot retained minimum service
    assert data["source_depot_impact"]["buses_remaining_at_depot"] >= 1


def test_schedule_persists_across_restart():
    """Verify that schedules saved in SQLite persist across new connections and restarts."""
    from app.database import get_db_connection

    token = get_admin_token()
    payload = {
        "event_name": "Persistence Verification Event",
        "event_date": "2026-10-30",
        "event_start_time": "19:00",
        "expected_crowd_departure": "2026-10-30T23:00",
        "depot_name": "Central Depot",
        "bus_number": "BUS-105",
        "bus_capacity": 70,
        "available_bus_count": 1,
        "source_stop": "Tech Hub North Stop",
        "destination_stop": "Main Bus Stand",
        "departure_time": "2026-10-30T22:15",
        "route_details": "Central Ring Route"
    }
    create_res = client.post("/api/schedules", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert create_res.status_code == 201
    created_id = create_res.json()["id"]

    # Open a completely fresh DB connection as if server restarted
    fresh_conn = get_db_connection()
    cursor = fresh_conn.cursor()
    cursor.execute("SELECT * FROM schedules WHERE id = ?", (created_id,))
    row = cursor.fetchone()
    fresh_conn.close()

    assert row is not None
    assert row["event_name"] == "Persistence Verification Event"
    assert row["bus_number"] == "BUS-105"
