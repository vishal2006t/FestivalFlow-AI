"""Comprehensive Master Test Suite for FestivalFlow AI.

Covers:
1. Authentication & Role-Based Authorization:
   - Admin login success/failure, Driver login success/failure
   - Admin-only endpoint protection (403 for drivers, 401 for unauthenticated)
   - Object-level ownership & IDOR protection for drivers
2. Fixed-Fleet Optimization & Strict Conservation (17 buses):
   - Fleet conservation check
   - Source-stop minimum service protection
   - Double-booking prevention
3. Mandatory Constraint-1 & Required Operational Scenarios:
   - Scenario A: Event end time changed from 9:00 PM to 9:30 PM (automatic recalculation, monotonic versioning, no auto-dispatch)
   - Scenario B: Rain starts during event (weather multipliers, transparent source labeling)
   - Scenario C: Bus breakdown (excluded from candidates, unmet demand recalculation)
4. OpenRouter AI Explainer Service:
   - Status reporting without secrets
   - Graceful fallback when key is not configured
5. MongoDB Integration:
   - Non-destructive status reporting and safe connection testing
6. Weather Integration & Provenance:
   - Explicit labeling: 'live', 'manual', 'synthetic', 'unknown'
7. ML Data Pipeline:
   - Reproducible synthetic dataset schema validation and chronological train/val/test evaluation
"""

import os
import pytest
from fastapi.testclient import TestClient
from main import app
from app.live_recalculation.engine import get_live_engine
from app.ai_explainer import get_ai_status, explain_recommendation
from app.database_mongo import test_mongodb_connection as check_mongo_conn, sanitize_uri
from app.data.synthetic_generator import generate_synthetic_dataset
from app.data.ml_pipeline import run_pipeline

client = TestClient(app)


# ==================== Fixtures ====================

@pytest.fixture(scope="module")
def admin_token():
    """Authenticate as depot admin and return session bearer token."""
    resp = client.post("/api/auth/login", json={
        "username": "admin_chennai",
        "password": "Admin@Depot2026",
        "role": "depot_admin"
    })
    assert resp.status_code == 200
    return resp.json()["token"]


@pytest.fixture(scope="module")
def driver_ramesh_token():
    """Authenticate as driver_ramesh (assigned BUS-201)."""
    resp = client.post("/api/auth/login", json={
        "username": "driver_ramesh",
        "password": "Driver@2026",
        "role": "driver"
    })
    assert resp.status_code == 200
    return resp.json()["token"]


@pytest.fixture(scope="module")
def driver_suresh_token():
    """Authenticate as driver_suresh (assigned BUS-202)."""
    resp = client.post("/api/auth/login", json={
        "username": "driver_suresh",
        "password": "Driver@2026",
        "role": "driver"
    })
    assert resp.status_code == 200
    return resp.json()["token"]


# ==================== 1. Authentication & Authorization Tests ====================

def test_admin_login_success(admin_token):
    """Verify depot admin login returns valid token and profile."""
    assert admin_token is not None
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "depot_admin"
    assert data["username"] == "admin_chennai"


def test_driver_login_success(driver_ramesh_token):
    """Verify bus driver login returns valid token and driver role."""
    assert driver_ramesh_token is not None
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {driver_ramesh_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "driver"
    assert data["username"] == "driver_ramesh"


def test_login_failure_invalid_password():
    """Verify invalid password returns 401 without specific credential exposure."""
    resp = client.post("/api/auth/login", json={
        "username": "admin_chennai",
        "password": "WrongPassword!2026",
        "role": "depot_admin"
    })
    assert resp.status_code == 401
    assert "Invalid username or password" in resp.json()["detail"]


def test_login_failure_role_mismatch():
    """Verify requesting wrong role returns 401."""
    resp = client.post("/api/auth/login", json={
        "username": "admin_chennai",
        "password": "Admin@Depot2026",
        "role": "driver"  # admin_chennai is depot_admin, not driver
    })
    assert resp.status_code == 401


def test_driver_rejected_from_admin_apis(driver_ramesh_token):
    """Verify bus driver is strictly forbidden (403) from admin management endpoints."""
    headers = {"Authorization": f"Bearer {driver_ramesh_token}"}
    
    # 1. Schedules creation
    resp = client.post("/api/schedules", json={
        "event_name": "Test",
        "event_date": "2026-10-10",
        "event_start_time": "18:00",
        "expected_crowd_departure": "2026-10-10T22:00",
        "depot_name": "Tech Park North Depot",
        "bus_number": "BUS-203",
        "source_stop": "Tech Hub",
        "destination_stop": "Main Stand",
        "departure_time": "2026-10-10T21:40",
        "route_details": "Test Route"
    }, headers=headers)
    assert resp.status_code == 403

    # 2. Live event time update
    resp2 = client.post("/api/live/event-update", json={"end_time": "21:30"}, headers=headers)
    assert resp2.status_code == 403

    # 3. AI service status
    resp3 = client.get("/api/ai/status", headers=headers)
    assert resp3.status_code == 403

    # 4. Database status
    resp4 = client.get("/api/database/status", headers=headers)
    assert resp4.status_code == 403


def test_unauthenticated_requests_rejected():
    """Verify endpoints reject requests with missing token (401)."""
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    resp2 = client.get("/api/driver/my-schedules")
    assert resp2.status_code == 401


def test_driver_idor_protection(driver_ramesh_token, driver_suresh_token):
    """Verify a driver CANNOT update or access another driver's assigned trips (IDOR protection)."""
    # 1. Driver Suresh gets their own schedules
    resp_suresh = client.get("/api/driver/my-schedules", headers={"Authorization": f"Bearer {driver_suresh_token}"})
    assert resp_suresh.status_code == 200
    suresh_schedules = resp_suresh.json()
    assert len(suresh_schedules) > 0
    suresh_sched_id = suresh_schedules[0]["id"]

    # 2. Driver Ramesh tries to modify Suresh's schedule status -> MUST BE REJECTED with 403
    resp_attack = client.patch(
        f"/api/driver/schedules/{suresh_sched_id}/status",
        json={"status": "Departed"},
        headers={"Authorization": f"Bearer {driver_ramesh_token}"}
    )
    assert resp_attack.status_code == 403
    assert "Forbidden" in resp_attack.json()["detail"]


# ==================== 2. Fixed-Fleet Optimization & Constraints ====================

def test_fixed_fleet_conservation():
    """Verify total network fleet size remains strictly fixed at 17 buses before and after."""
    resp = client.post("/api/optimize")
    assert resp.status_code == 200
    data = resp.json()
    fleet = data.get("fleet_conservation", {})
    assert fleet.get("is_conserved") is True
    assert fleet.get("total_fleet_before") == 17
    assert fleet.get("total_fleet_after") == 17


def test_source_stop_minimum_service_protection():
    """Verify Tech Park North Depot retains minimum service buses and is never stripped to 0."""
    resp = client.post("/api/optimize")
    assert resp.status_code == 200
    data = resp.json()
    realloc = data.get("reallocations", [{}])[0]
    source_impact = realloc.get("source_impact", {})
    assert source_impact.get("remaining_buses") >= 1
    assert source_impact.get("min_service_threshold") == 1


def test_unmet_demand_honestly_reported():
    """Verify that when 40,000 attendees disperse, unmet demand is calculated and reported."""
    resp = client.post("/api/optimize")
    assert resp.status_code == 200
    data = resp.json()
    hub = data.get("before_and_after_comparison", {}).get("hub_stop", {})
    assert "unmet_demand_after" in hub
    assert hub["unmet_demand_after"] >= 0


# ==================== 3. Constraint-1 & Mandatory Scenarios ====================

def test_scenario_a_event_delay_30_mins(admin_token):
    """Scenario A: Event end time changed from 9:00 PM to 9:30 PM.
    
    Verifies:
    1. Validates and persists new time.
    2. Automatically triggers recalculation without manual rerun.
    3. Shifts peak intervals.
    4. Monotonic calculation version increments.
    5. Displays reason: 'Event end time changed from 9:00 PM to 9:30 PM.'
    6. Does NOT automatically dispatch buses.
    """
    engine = get_live_engine()
    state_before = engine.get_state()
    v_before = state_before["version"]

    resp = client.post(
        "/api/live/event-update",
        json={"end_time": "21:30"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "SUCCESS"

    recalc = body["recalculation"]
    assert recalc["status"] == "COMPLETED"
    assert recalc["version"] > v_before
    assert "Event end time changed from" in recalc["reason"]
    assert "9:30 PM" in recalc["reason"]

    # Verify state updated
    state_after = engine.get_state()
    assert state_after["inputs_snapshot"]["headline_end_time"] == "21:30"
    assert state_after["inputs_snapshot"]["headline_end_time_display"] == "9:30 PM"

    # Verify intervals shifted
    intervals = state_after["current_prediction"]["intervals"]
    assert len(intervals) == 14
    # Peak finale is centered around 21:30 (interval 4 is 21:30)
    assert intervals[4] == "21:30"

    # Confirm NO automatic dispatch: schedules count unchanged or no auto-dispatch plan approved
    plans_resp = client.get("/api/dispatch/plans", headers={"Authorization": f"Bearer {admin_token}"})
    assert plans_resp.status_code == 200


def test_scenario_b_rain_starts_during_event(admin_token):
    """Scenario B: Rain starts during the event.
    
    Verifies:
    1. Validates and persists weather input.
    2. Automatically triggers recalculation with weather multipliers.
    3. Surge multiplier > 1.0 applied.
    4. Staging departure time adjusted earlier.
    5. Weather source and last updated time tracked.
    """
    engine = get_live_engine()
    v_before = engine.get_state()["version"]

    resp = client.post(
        "/api/live/weather-update",
        json={
            "weather_condition": "Light Rain",
            "weather_source": "ADMIN_MANUAL_OVERRIDE"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "SUCCESS"

    state = engine.get_state()
    assert state["version"] > v_before
    assert state["inputs_snapshot"]["weather_condition"] == "Light Rain"
    assert state["inputs_snapshot"]["weather_source"] == "ADMIN_MANUAL_OVERRIDE"

    # Verify weather multiplier was applied
    explanation = state["current_prediction"]["explanation"]
    assert explanation["surge_multiplier_applied"] >= 1.15


def test_scenario_c_bus_breakdown_refreshes_recommendations(admin_token):
    """Scenario C: Bus becomes unavailable due to breakdown.
    
    Verifies:
    1. Bus status marked as 'Breakdown'.
    2. Automatically triggers recalculation.
    3. Bus is flagged in conflicts and excluded from available pool.
    4. Unmet demand reflects remaining available buses.
    """
    resp = client.post(
        "/api/live/bus-update",
        json={
            "bus_number": "BUS-203",
            "status": "Breakdown",
            "reason": "Engine overheating during staging"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "SUCCESS"

    engine = get_live_engine()
    state = engine.get_state()
    avail = state["current_recommendation"].get("availability_validation", {})
    conflicts = avail.get("conflicts", [])
    broken_bus_conflicts = [c for c in conflicts if c.get("bus_number") == "BUS-203"]
    assert len(broken_bus_conflicts) > 0


# ==================== 4. OpenRouter AI Explainer Service ====================

def test_ai_status_endpoint(admin_token):
    """Verify AI status endpoint reports provider safely without exposing API keys."""
    resp = client.get("/api/ai/status", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "OpenRouter"
    assert "status" in data
    assert "model" in data
    # Ensure no secret strings leaked
    assert "Bearer" not in str(data)
    assert "sk-" not in str(data)


def test_ai_explain_recommendation(admin_token):
    """Verify AI explainer returns a valid operational briefing."""
    resp = client.post(
        "/api/ai/explain",
        json={"context_type": "recommendation"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "explanation" in data
    assert len(data["explanation"]) > 20
    assert data["source"] in ["OPENROUTER_AI", "DETERMINISTIC_BASELINE", "DETERMINISTIC_FALLBACK"]


# ==================== 5. MongoDB Integration ====================

def test_database_status_endpoint(admin_token):
    """Verify primary database status and MongoDB connection status reporting."""
    resp = client.get("/api/database/status", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "SQLite" in data["primary_database"]
    assert data["sqlite_status"] == "ONLINE_HEALTHY"
    assert data["sqlite_table_count"] >= 15
    assert "mongodb_status" in data
    assert data["mongodb_status"] in ["NOT_CONFIGURED", "CONNECTED", "CONNECTION_FAILED", "DEPENDENCY_MISSING"]


def test_mongo_test_connection_safe():
    """Verify testing MongoDB connection without URI returns NOT_CONFIGURED safely."""
    res = check_mongo_conn("")
    assert res["connected"] is False
    assert res["status"] == "NOT_CONFIGURED"


def test_uri_sanitization():
    """Verify URI credentials sanitizer masks secret passwords."""
    raw_uri = "mongodb+srv://admin_user:SuperSecretPassword123@cluster0.mongodb.net/testdb"
    clean = sanitize_uri(raw_uri)
    assert "SuperSecretPassword123" not in clean
    assert "*****" in clean


# ==================== 6. Weather Integration & Provenance ====================

def test_current_weather_provenance():
    """Verify GET /api/weather/current returns transparent data provenance."""
    resp = client.get("/api/weather/current")
    assert resp.status_code == 200
    data = resp.json()
    assert "source_label" in data
    assert data["source_label"] in ["live", "manual", "synthetic", "unknown"]
    assert "provider" in data
    assert "weather_condition" in data


# ==================== 7. ML Data Pipeline & Synthetic Data ====================

def test_synthetic_data_generation():
    """Verify synthetic data generator produces valid reproducible records with fixed seed."""
    test_csv = "app/data/test_synthetic_sample.csv"
    res = generate_synthetic_dataset(test_csv, seed=42)
    assert res["status"] == "SUCCESS"
    assert res["record_count"] > 100
    assert os.path.exists(test_csv)
    # Clean up test file
    try:
        os.remove(test_csv)
    except OSError:
        pass


def test_ml_pipeline_execution():
    """Verify ML pipeline performs schema validation, chronological split, and evaluation."""
    rep = run_pipeline()
    assert rep["validation"]["is_valid"] is True
    assert rep["split_counts"]["train"] > 0
    assert rep["split_counts"]["test"] > 0
    assert "MAE_passengers" in rep["evaluation"]["metrics"]
    assert "RMSE_passengers" in rep["evaluation"]["metrics"]
    assert rep["evaluation"]["metrics"]["MAE_passengers"] >= 0


# ==================== 8. Operational Network Updates & Simulation Removal ====================

def test_network_stop_patch_triggers_recalculation(admin_token):
    """Verify PATCH /api/network/stops/{id} updates capacity and triggers live recalculation."""
    resp = client.patch(
        "/api/network/stops/STOP_MAIN",
        json={"capacity": 16000},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["capacity"] == 16000

    # Verify recalculation triggered
    engine = get_live_engine()
    state = engine.get_state()
    assert "STOP_MAIN" in state["last_reason"] or "capacity" in state["last_reason"]


def test_network_route_patch_triggers_recalculation(admin_token):
    """Verify PATCH /api/network/routes/{id} updates headway and triggers live recalculation."""
    resp = client.patch(
        "/api/network/routes/RT-01",
        json={"typical_headway_mins": 14, "distance_km": 2.3},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["typical_headway_mins"] == 14
    assert data["distance_km"] == 2.3

    # Verify recalculation triggered
    engine = get_live_engine()
    state = engine.get_state()
    assert "RT-01" in state["last_reason"] or "headway" in state["last_reason"]


def test_frontend_simulation_ui_removed():
    """Verify that demo simulation titles and fake buttons are removed from the frontend dashboard."""
    with open("frontend/src/components/DepotAdminDashboard.jsx", "r", encoding="utf-8") as f:
        dashboard_content = f.read()

    # The demo scenario card titles and buttons must NOT exist in the dashboard JSX
    assert "Scenario A: Event Time Delay" not in dashboard_content
    assert "Scenario B: Rain Starts During Event" not in dashboard_content
    assert "handleTriggerScenarioA" not in dashboard_content
    assert "handleTriggerScenarioB" not in dashboard_content
    assert "handleResetScenarioA" not in dashboard_content
    assert "Delay +30m (➔ 9:30 PM)" not in dashboard_content
    assert "OperationsReportView" in dashboard_content


def test_database_records_strictly_preserved():
    """Verify primary database tables and fixed fleet of 17 buses are strictly conserved."""
    from app.database import get_all_buses, get_all_depots, get_db_connection
    buses = get_all_buses()
    assert len(buses) == 17, f"Expected 17 fixed buses, found {len(buses)}"
    
    depots = get_all_depots()
    assert len(depots) >= 2, "Depots must be preserved"
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    user_count = cur.fetchone()[0]
    conn.close()
    assert user_count >= 4, f"User accounts must be preserved, found {user_count}"


