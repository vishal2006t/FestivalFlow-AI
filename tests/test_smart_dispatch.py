"""Tests for Bus Occupancy, Route Matching Recommender, Night Safety Alerts, and Driver Notifications."""

import pytest
from fastapi.testclient import TestClient
from main import app
from app.database import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure clean database state before each test."""
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


def test_bus_telematics_occupancy_tracking():
    """Bus telematics lists all 17 buses with capacity, available seats, and data provenance."""
    token = get_admin_token()
    res = client.get("/api/buses/telematics", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    buses = res.json()
    assert len(buses) == 17

    # Verify BUS-203 has realistic sensor occupancy
    bus203 = next(b for b in buses if b["bus_number"] == "BUS-203")
    assert bus203["capacity"] == 70
    assert bus203["available_seats"] == 58
    assert bus203["passenger_count"] == 12
    assert "SENSOR" in bus203["occupancy_source"]


def test_smart_dispatch_recommender_finds_underutilized_bus():
    """Smart Dispatch evaluates candidate buses and recommends an underutilized bus with trade-off analysis."""
    token = get_admin_token()
    payload = {
        "target_stop_id": "STOP_MAIN",
        "crowd_count": 145,
        "crowd_trend": "Surging",
        "is_night_time": True
    }
    res = client.post("/api/smart-dispatch/recommend", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "RECOMMENDATION_READY"
    assert data["target_stop_id"] == "STOP_MAIN"
    assert "Fixed Fleet: 17 Buses" in data["fleet_constraint"]

    # Recommends underutilized bus BUS-203 or BUS-204
    top_bus = data["top_candidate"]
    assert top_bus["bus_number"] in ["BUS-203", "BUS-204"]
    assert top_bus["available_seats"] >= 50
    assert top_bus["occupancy_rate"] < 0.30  # underutilized

    # Excludes full bus BUS-205 (>85% occupancy)
    rejected_numbers = [r["bus_number"] for r in data["rejected_options"]]
    assert "BUS-205" in rejected_numbers

    # Source impact details
    assert "source_impact" in data
    assert "headway_change" in data["source_impact"]
    assert "COMPLIANT" in data["source_impact"]["minimum_service_status"]


def test_night_safety_alert_generation():
    """System surfaces Night Safety alert when night queue exceeds safety duration threshold."""
    token = get_admin_token()
    res = client.get("/api/alerts?night_safety_only=true", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    alerts = res.json()
    assert len(alerts) >= 1

    night_alert = alerts[0]
    assert night_alert["alert_type"] == "NIGHT_SAFETY"
    assert night_alert["severity"] in ["CRITICAL", "HIGH"]
    assert night_alert["is_night_time"] == 1
    assert night_alert["waiting_time_mins"] >= 15
    assert "Night Safety Alert" in night_alert["message"]


def test_depot_admin_notifies_driver_and_driver_receives_alert():
    """Depot Admin sends urgent Night Safety clearance run alert to assigned Bus Driver."""
    admin_token = get_admin_token()

    # 1. Get driver user ID for driver_ramesh
    driver_res = client.get("/api/drivers", headers={"Authorization": f"Bearer {admin_token}"})
    ramesh = next(d for d in driver_res.json() if "Ramesh" in d["driver_name"])

    # 2. Get active alert ID
    alerts = client.get("/api/alerts", headers={"Authorization": f"Bearer {admin_token}"}).json()
    alert_id = alerts[0]["id"]

    # 3. Admin dispatches notification to driver
    notify_payload = {
        "driver_id": ramesh["user_id"],
        "custom_message": "Urgent Night Clearance: Proceed to Bay 3 for Main Bus Stand surge."
    }
    notify_res = client.post(f"/api/alerts/{alert_id}/notify-driver", json=notify_payload, headers={"Authorization": f"Bearer {admin_token}"})
    assert notify_res.status_code == 200
    assert notify_res.json()["status"] == "NOTIFIED"

    # 4. Driver logs in and retrieves urgent notification
    driver_token = get_driver_token("driver_ramesh")
    notif_res = client.get("/api/driver/my-notifications", headers={"Authorization": f"Bearer {driver_token}"})
    assert notif_res.status_code == 200
    notifications = notif_res.json()
    assert len(notifications) >= 1

    latest_notif = notifications[0]
    assert latest_notif["notification_type"] == "NIGHT_SAFETY_DISPATCH"
    assert "Urgent Night Clearance" in latest_notif["message"]

    # 5. Driver marks notification as read
    read_res = client.patch(f"/api/driver/notifications/{latest_notif['id']}/read", headers={"Authorization": f"Bearer {driver_token}"})
    assert read_res.status_code == 200
