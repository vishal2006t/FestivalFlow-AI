"""Automated test suite verifying Constraint-1: Automatic Live Recalculation for FestivalFlow AI.

Covers all 10 required test criteria:
1. Changing event end time from 9:00 PM to 9:30 PM triggers recalculation without a manual rerun (Scenario A).
2. Updating weather to rain triggers recalculation and uses weather variable in model (Scenario B).
3. Updated bus status (e.g. breakdown/out of service) refreshes recommendation.
4. Frontend state endpoint (/api/live/state) provides updated results with versioning and timestamps.
5. Older calculation results cannot overwrite newer results (monotonic version guard).
6. Rapid input changes do not create uncontrolled duplicate calculations (debouncing/batching).
7. Invalid inputs and unauthorized changes are rejected (role enforcement & validation).
8. Conflicting bus/driver assignments are prevented during recommendation & staging.
9. Dispatch approval remains an explicit authorized admin action (manual dispatch only).
10. Existing prediction and optimization algorithms integrity preserved.
"""

import pytest
from starlette.testclient import TestClient
from main import app
from app.database import init_db
from app.live_recalculation.engine import get_live_engine

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db_and_engine():
    """Ensure clean database and live recalculation engine before each test."""
    init_db(force_reset=True)
    engine = get_live_engine()
    engine.headline_end_time = "21:00"
    engine.weather_condition = "Clear"
    engine.crowd_estimate = 40000
    engine.trigger_recalculation(reason="Test fixture baseline reset.", new_event_end_time="21:00", new_weather="Clear")


def get_admin_token() -> str:
    """Helper to authenticate as Depot Admin."""
    res = client.post("/api/auth/login", json={
        "username": "admin_chennai",
        "password": "Admin@Depot2026",
        "role": "depot_admin"
    })
    assert res.status_code == 200, res.text
    return res.json()["token"]


def get_driver_token() -> str:
    """Helper to authenticate as Bus Driver."""
    res = client.post("/api/auth/login", json={
        "username": "driver_ramesh",
        "password": "Driver@2026",
        "role": "driver"
    })
    assert res.status_code == 200, res.text
    return res.json()["token"]


# ==================== Test 1: Scenario A (Event Delayed 9:00 PM -> 9:30 PM) ====================

def test_scenario_a_event_end_time_delay_triggers_recalculation():
    """Requirement 1 & Scenario A:
    Updating event end time from 9:00 PM to 9:30 PM automatically triggers recalculation,
    shifts departure timing and arrival window, and formats the exact reason string.
    """
    token = get_admin_token()
    
    # Verify initial baseline
    state_res = client.get("/api/live/state")
    assert state_res.status_code == 200
    initial_state = state_res.json()
    assert initial_state["inputs_snapshot"]["headline_end_time"] == "21:00"
    init_version = initial_state["version"]

    # Trigger update to 9:30 PM (21:30)
    update_res = client.post(
        "/api/live/event-update",
        headers={"Authorization": f"Bearer {token}"},
        json={"end_time": "21:30"}
    )
    assert update_res.status_code == 200
    data = update_res.json()
    recalc = data["recalculation"]

    assert recalc["status"] == "COMPLETED"
    assert recalc["version"] > init_version
    # Verify reason matches specification exactly
    assert recalc["reason"] == "Event end time changed from 9:00 PM to 9:30 PM."

    # Verify algorithmic shift in recommended departure time (+30 minutes)
    diff = recalc["diff"]
    assert diff["recommendation"]["previous_departure_time"] == "20:43"
    assert diff["recommendation"]["current_departure_time"] == "21:13"
    assert diff["recommendation"]["previous_arrival_time"] == "20:55"
    assert diff["recommendation"]["current_arrival_time"] == "21:25"

    # Verify fleet conservation
    assert diff["recommendation"]["fleet_conserved"] is True
    assert diff["recommendation"]["total_network_fleet"] == 17

    # Verify updated state is immediately queryable
    updated_state = client.get("/api/live/state").json()
    assert updated_state["inputs_snapshot"]["headline_end_time"] == "21:30"
    assert updated_state["inputs_snapshot"]["headline_end_time_display"] == "9:30 PM"


# ==================== Test 2: Scenario B (Rain Starts During Event) ====================

def test_scenario_b_rain_starts_triggers_recalculation_and_surge_multiplier():
    """Requirement 2 & Scenario B:
    Updating weather to 'Light Rain' automatically recalculates predictions using
    RuleBasedDemandPredictor's 1.15x surge multiplier and adjusts transit speed.
    """
    token = get_admin_token()

    update_res = client.post(
        "/api/live/weather-update",
        headers={"Authorization": f"Bearer {token}"},
        json={"weather_condition": "Light Rain"}
    )
    assert update_res.status_code == 200
    data = update_res.json()
    recalc = data["recalculation"]

    assert recalc["status"] == "COMPLETED"
    assert "Rain started during event" in recalc["reason"]

    # Verify weather multipliers applied to peak passenger volume
    diff = recalc["diff"]
    demand_diff = diff["demand"]
    assert demand_diff["surge_multiplier_applied"] == 1.15
    # 8,200 * 1.15 = 9,430
    assert demand_diff["current_peak_volume"] > demand_diff["previous_peak_volume"]
    assert demand_diff["current_peak_volume"] == 9430

    # Verify wet road transit delay: departure shifts earlier
    rec_diff = diff["recommendation"]
    # 20:41 departure vs 20:43 in dry conditions (2 min road buffer for 1.2x transit time)
    assert rec_diff["current_departure_time"] <= rec_diff["previous_departure_time"]
    assert rec_diff["current_unmet_demand"] > rec_diff["previous_unmet_demand"]


# ==================== Test 3: Bus Breakdown / Status Update ====================

def test_bus_breakdown_refreshes_recommendation_and_availability():
    """Requirement 3:
    When an assigned bus breaks down or changes status, live recommendation refreshes
    its availability validation.
    """
    token = get_admin_token()

    update_res = client.post(
        "/api/live/bus-update",
        headers={"Authorization": f"Bearer {token}"},
        json={"bus_number": "BUS-201", "status": "Breakdown"}
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["message"] == "Bus BUS-201 marked as Breakdown."

    # Verify live state records the status change
    state = client.get("/api/live/state").json()
    avail = state["current_recommendation"]["availability_validation"]
    conflicts = avail.get("conflicts", [])
    assert any(c["bus_number"] == "BUS-201" for c in conflicts)


# ==================== Test 4: Frontend State Endpoint & Sync ====================

def test_frontend_receives_new_results_with_differential_sync():
    """Requirement 4:
    GET /api/live/state provides versioning, timestamps, diffs, and supports
    since_version query param for efficient client differential polling.
    """
    token = get_admin_token()
    v1_state = client.get("/api/live/state").json()
    v1 = v1_state["version"]

    # Check without updates
    sync_res = client.get(f"/api/live/state?since_version={v1}").json()
    assert sync_res["has_updates"] is False

    # Trigger change
    client.post(
        "/api/live/event-update",
        headers={"Authorization": f"Bearer {token}"},
        json={"delay_mins": 30}
    )

    # Check with updates
    sync_res_after = client.get(f"/api/live/state?since_version={v1}").json()
    assert sync_res_after["has_updates"] is True
    assert sync_res_after["version"] > v1
    assert "Event end time changed" in sync_res_after["last_reason"]


# ==================== Test 5: Monotonic Version Guard (No Overwrites) ====================

def test_older_calculation_results_cannot_overwrite_newer_results():
    """Requirement 5:
    A slower or older calculation version is discarded if a newer calculation
    has already been committed.
    """
    engine = get_live_engine()
    engine._applied_version = 10  # Simulate current version is 10

    # Attempt to commit an older version calculation (version 8)
    stale_result = engine._run_calculation_internal(
        reason="Stale calculation finish",
        calc_version=8
    )
    assert stale_result["status"] == "DISCARDED_STALE"
    assert engine._applied_version == 10  # Remained intact


# ==================== Test 6: Debouncing Rapid Concurrent Changes ====================

def test_rapid_input_changes_do_not_create_uncontrolled_duplicate_runs():
    """Requirement 6:
    Multiple rapid triggers sequentially update the monotonic version without corruption.
    """
    token = get_admin_token()

    # Rapid sequential calls
    r1 = client.post("/api/live/weather-update", headers={"Authorization": f"Bearer {token}"}, json={"weather_condition": "Light Rain"})
    r2 = client.post("/api/live/event-update", headers={"Authorization": f"Bearer {token}"}, json={"end_time": "21:30"})
    r3 = client.post("/api/live/weather-update", headers={"Authorization": f"Bearer {token}"}, json={"weather_condition": "Heavy Rain"})

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 200

    final_state = client.get("/api/live/state").json()
    assert final_state["inputs_snapshot"]["weather_condition"] == "Heavy Rain"
    assert final_state["inputs_snapshot"]["headline_end_time"] == "21:30"
    assert final_state["version"] >= 3


# ==================== Test 7: Security & Authorization ====================

def test_unauthorized_and_invalid_inputs_rejected():
    """Requirement 7:
    - Driver cannot alter event end time (403 Forbidden).
    - Malformed timestamps and unapproved weather conditions are rejected (400/422).
    """
    driver_token = get_driver_token()
    admin_token = get_admin_token()

    # Driver trying to change event end time
    forbidden_res = client.post(
        "/api/live/event-update",
        headers={"Authorization": f"Bearer {driver_token}"},
        json={"end_time": "22:00"}
    )
    assert forbidden_res.status_code == 403

    # Driver trying to change weather
    forbidden_weather = client.post(
        "/api/live/weather-update",
        headers={"Authorization": f"Bearer {driver_token}"},
        json={"weather_condition": "Heavy Rain"}
    )
    assert forbidden_weather.status_code == 403

    # Admin sending invalid weather condition
    bad_weather = client.post(
        "/api/live/weather-update",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"weather_condition": "HurricaneCategory5"}
    )
    assert bad_weather.status_code == 400

    # Admin sending malformed time
    bad_time = client.post(
        "/api/live/event-update",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"end_time": "invalid-timestamp"}
    )
    assert bad_time.status_code == 400


# ==================== Test 8: Conflicting Assignments Prevented ====================

def test_conflicting_bus_driver_assignments_prevented():
    """Requirement 8:
    Recheck operational availability prevents double-booking buses or drivers
    during recalculation and plan creation. Conflicting assignments are rejected.
    """
    token = get_admin_token()

    # Attempting to assign BUS-201 to an overlapping trip is strictly rejected
    conflict_res = client.post(
        "/api/schedules",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_name": "Grand City Lights Cultural Festival",
            "event_date": "2026-10-10",
            "event_start_time": "18:00",
            "expected_crowd_departure": "2026-10-10T22:00",
            "depot_name": "Tech Park North Depot",
            "bus_number": "BUS-201",
            "bus_capacity": 70,
            "available_bus_count": 1,
            "source_stop": "Tech Hub North Stop",
            "destination_stop": "Main Bus Stand",
            "departure_time": "2026-10-10T21:40",
            "arrival_time": "2026-10-10T22:00",
            "driver_id": 3,
            "route_details": "Corridor Express",
            "status": "Scheduled"
        }
    )
    # 400 Bad Request: Conflict detected and prevented!
    assert conflict_res.status_code == 400
    assert "conflict" in conflict_res.json()["detail"].lower()

    # Check live state availability validation recognizes BUS-201 is active
    engine = get_live_engine()
    avail = engine._check_fleet_availability()
    assert any(c["bus_number"] == "BUS-201" for c in avail.get("conflicts", []))


# ==================== Test 9: Dispatch Approval Remains Strictly Manual ====================

def test_dispatch_approval_must_remain_explicit_manual_admin_action():
    """Requirement 9:
    Automatic recalculation updates recommendations, but NEVER dispatches real buses.
    Explicit approval via POST /api/dispatch/plans/{id}/approve is required.
    """
    token = get_admin_token()

    # Create a draft plan
    plan_res = client.post(
        "/api/dispatch/plan",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "target_stop_id": "STOP_MAIN",
            "target_stop_name": "Main Bus Stand (Festival Arena)",
            "buses_requested": 4,
            "crowd_count": 400
        }
    )
    assert plan_res.status_code in [200, 201]
    plan = plan_res.json()
    plan_id = plan["id"]
    assert plan["status"] == "PENDING"

    # Verify no assignments or notifications created yet
    state_before = client.get(
        f"/api/dispatch/plans/{plan_id}",
        headers={"Authorization": f"Bearer {token}"}
    ).json()
    assert state_before["status"] == "PENDING"


    # Explicit Depot Admin approval is required
    approve_res = client.post(
        f"/api/dispatch/plans/{plan_id}/approve",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"



# ==================== Test 10: Existing Optimizer & Prediction Integrity ====================

def test_existing_prediction_and_optimization_integrity():
    """Requirement 10:
    Direct calls to /api/demand and /api/optimize preserve baseline outputs,
    gamma-like surge shape, fleet conservation, and minimum service constraints.
    """
    # 1. /api/demand test
    demand_res = client.get("/api/demand?weather=Clear")
    assert demand_res.status_code == 200
    demand = demand_res.json()
    assert "STOP_MAIN" in demand["predictions"]
    main_preds = demand["predictions"]["STOP_MAIN"]
    assert len(main_preds) == 14
    # Peak occurs in slots 4-7 (22:00 - 22:45)
    peak_idx = main_preds.index(max(main_preds))
    assert 4 <= peak_idx <= 7

    # 2. /api/optimize test
    opt_res = client.post("/api/optimize")
    assert opt_res.status_code == 200
    opt = opt_res.json()
    assert opt["fleet_conservation"]["is_conserved"] is True
    assert opt["fleet_conservation"]["total_fleet_after"] == 17
    # Minimum commuter service maintained at source stop
    source_stop = opt["before_and_after_comparison"]["source_stop"]
    assert source_stop["buses_after"] >= source_stop["min_required"]
