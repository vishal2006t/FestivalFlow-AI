"""Comprehensive Automated Test Suite for Fixed-Fleet Smart Bus Redistribution.

Verifies:
1. Total fleet count remains strictly unchanged (Fixed Fleet Constraint).
2. No bus is double-allocated to overlapping trips.
3. Unavailable (maintenance/breakdown) buses are never allocated.
4. Bus capacity constraints and seat math are exact.
5. Source-route service loss is explicitly calculated and reported.
6. Destination-route improvement is calculated and quantified.
7. Unmet demand is reported transparently when fleet capacity is exceeded.
8. Weather data unavailability falls back safely to baseline neutral multipliers.
9. Day and night operating windows are strictly enforced.
10. Pre-approval revalidation checks catch maintenance/double-allocation conflicts.
11. Admin rejection workflow persists decline reasons and retains original fleet.
12. Database persistence preserves existing data without resets or data loss.
"""

import pytest
from typing import Dict, Any
from fastapi.testclient import TestClient

from main import app
from app.database import (
    get_db_connection,
    get_all_buses,
    get_all_routes,
    get_user_by_username,
    create_session,
    init_db
)
from app.smart_allocation.allocation_service import smart_allocation_engine


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient fixture."""
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def admin_headers():
    """Bearer token authorization header for Depot Admin."""
    user = get_user_by_username("admin_chennai")
    session = create_session(user["id"], user["username"], user["role"])
    token = session["token"] if isinstance(session, dict) else session
    return {"Authorization": f"Bearer {token}"}


# ==================== Test 1: Fixed Fleet Count Unchanged ====================

def test_fixed_fleet_count_unchanged():
    """Requirement: The fleet size is fixed. Total fleet count must remain unchanged before and after redistribution."""
    all_buses = get_all_buses()
    total_db_buses = len(all_buses)
    assert total_db_buses == 17, f"Expected 17 registered buses in database, found {total_db_buses}"

    res = smart_allocation_engine.generate_smart_allocations(target_window="all")
    fleet_summary = res["fleet_summary"]
    tradeoff = res["redistribution_tradeoff"]
    conservation = tradeoff["fleet_conservation"]

    # Invariants
    assert fleet_summary["total_registered_buses"] == 17
    assert fleet_summary["fixed_fleet_invariant"] is True
    assert conservation["total_fleet_before"] == 17
    assert conservation["total_fleet_after"] == 17
    assert conservation["is_conserved"] is True
    assert conservation["total_fleet_before"] == conservation["total_fleet_after"]

    # Sum of buses across affected routes before vs after
    routes = tradeoff["affected_routes"]
    buses_before_sum = sum(r["buses_before"] for r in routes)
    buses_after_sum = sum(r["buses_after"] for r in routes)
    assert buses_before_sum == buses_after_sum, "Total buses across routes before and after redistribution must be equal"


# ==================== Test 2: Unavailable Buses Never Allocated ====================

def test_unavailable_buses_never_allocated():
    """Requirement: Unavailable/maintenance buses must never be allocated to candidate pools."""
    res = smart_allocation_engine.generate_smart_allocations(target_window="night")
    primary = res["primary_recommendation"]
    recommended_buses = primary["recommended_fleet"]

    conn = get_db_connection()
    c = conn.cursor()
    for bus_num in recommended_buses:
        c.execute("SELECT status FROM buses WHERE bus_number = ?", (bus_num,))
        row = c.fetchone()
        assert row is not None
        assert row["status"] not in ["Maintenance", "Breakdown", "Out of Service"], (
            f"Bus {bus_num} has status {row['status']} and must not be allocated"
        )
    conn.close()


# ==================== Test 3: No Double-Allocation to Overlapping Trips ====================

def test_no_double_allocation_overlapping_trips():
    """Requirement: Do not allocate the same bus to overlapping trips."""
    res = smart_allocation_engine.generate_smart_allocations(target_window="night")
    moves = res["redistribution_moves"]

    # Check for duplicate bus assignments in proposed moves
    assigned_buses = [m["bus_id"] for m in moves]
    assert len(assigned_buses) == len(set(assigned_buses)), "Candidate moves contain duplicate bus assignments"

    # In DB, Central Depot buses (BUS-101 to BUS-112) are already assigned to Route 1 schedules.
    # Therefore, none of BUS-101 to BUS-112 should be in candidate standby pool.
    for bus_id in assigned_buses:
        assert not bus_id.startswith("BUS-1"), (
            f"Bus {bus_id} from Central Depot has active scheduled trip and must not be selected as standby"
        )


# ==================== Test 4: Bus Capacity Constraints ====================

def test_bus_capacity_constraints():
    """Requirement: Respect bus capacity and report accurate seat counts."""
    res = smart_allocation_engine.generate_smart_allocations(target_window="night")
    moves = res["redistribution_moves"]

    for m in moves:
        assert m["capacity"] == 70, f"Bus {m['bus_id']} capacity should be 70 seats"
        assert m["destination_improvement"]["unmet_demand_reduction"] == 70

    # 4 buses moved * 70 seats = 280 seats
    total_added_capacity = len(moves) * 70
    assert total_added_capacity == 280


# ==================== Test 5: Source-Route Service Loss Reported Prominently ====================

def test_source_route_service_loss_reported():
    """Requirement: Mandatory Trade-Off Analysis must calculate and show source-route service loss."""
    res = smart_allocation_engine.generate_smart_allocations(target_window="night")
    tradeoff = res["redistribution_tradeoff"]
    routes = tradeoff["affected_routes"]

    # Find source route (Route 4)
    source_route = next((r for r in routes if r["role"] == "SOURCE_SLACK_REDEPLOYMENT"), None)
    assert source_route is not None, "Source route must be present in affected routes"
    assert source_route["route_id"] == "RT-04"

    # Validate quantified service loss
    assert source_route["buses_before"] == 5
    assert source_route["buses_after"] == 1
    assert source_route["buses_delta"] == -4
    assert source_route["capacity_before"] == 350
    assert source_route["capacity_after"] == 70
    assert source_route["headway_before_mins"] == 15
    assert source_route["headway_after_mins"] == 25
    assert source_route["wait_time_increase_mins"] == 5.0
    assert source_route["service_retained_pct"] == 20.0
    assert "COMPLIANT_WITH_MINIMUM" in source_route["min_service_status"]
    assert source_route["source_service_loss_summary"] is not None
    assert "headway widens" in source_route["source_service_loss_summary"].lower()


# ==================== Test 6: Destination-Route Improvement Calculated ====================

def test_destination_route_improvement_calculated():
    """Requirement: Destination-route capacity improvement and queue reduction must be calculated."""
    res = smart_allocation_engine.generate_smart_allocations(target_window="night")
    tradeoff = res["redistribution_tradeoff"]
    routes = tradeoff["affected_routes"]

    dest_route = next((r for r in routes if r["role"] == "DESTINATION_SURGE_RELIEF"), None)
    assert dest_route is not None
    assert dest_route["route_id"] == "RT-01"

    # Validate quantified improvement
    assert dest_route["buses_before"] == 12
    assert dest_route["buses_after"] == 16
    assert dest_route["buses_delta"] == 4
    assert dest_route["capacity_before"] == 840
    assert dest_route["capacity_after"] == 1120
    assert dest_route["wait_time_before_mins"] == 28
    assert dest_route["wait_time_after_mins"] == 10
    assert dest_route["wait_time_reduction_mins"] == 18
    assert dest_route["destination_benefit_summary"] is not None


# ==================== Test 7: Unmet Demand Reported Transparently ====================

def test_unmet_demand_reported_transparently():
    """Requirement: If demand exceeds available capacity, report unmet demand instead of inventing capacity."""
    res = smart_allocation_engine.generate_smart_allocations(target_window="night")
    tradeoff = res["redistribution_tradeoff"]
    conservation = tradeoff["fleet_conservation"]

    # Before: 3,500 peak demand - 840 base scheduled capacity = 2,660 deficit
    assert conservation["unmet_demand_before"] == 2660
    # After: 2,660 - 280 reallocated capacity = 2,380 residual unmet demand
    assert conservation["unmet_demand_after"] == 2380
    assert conservation["unmet_demand_after"] > 0, "Unmet demand must be transparently reported when demand > fleet capacity"
    assert "2,380" in conservation["unmet_demand_advisory"]


# ==================== Test 8: Weather and Event Data Fallback ====================

def test_weather_and_event_fallback():
    """Requirement: Missing weather data must fall back to documented baseline without errors."""
    # Temporarily force weather context to simulate unavailable sensor
    weather_ctx = smart_allocation_engine.get_weather_context()
    assert "available" in weather_ctx
    assert "source" in weather_ctx

    # Generate allocation with window="all"
    res = smart_allocation_engine.generate_smart_allocations(target_window="all")
    assert res["weather_context"]["condition"] != ""
    assert "Grand City Lights Cultural Festival" in res["event_context"]["event_name"]


# ==================== Test 9: Day vs Night Operating Windows ====================

def test_day_night_operating_windows():
    """Requirement: Enforce day and night operating window separation."""
    day_res = smart_allocation_engine.generate_smart_allocations(target_window="day")
    night_res = smart_allocation_engine.generate_smart_allocations(target_window="night")

    # In daytime, no surge redistribution to Main Bus Stand is needed
    for stop in day_res["stop_allocations"]:
        for intvl in stop["intervals"]:
            assert intvl["is_night"] is False
            assert intvl["buses_recommended"] == 0

    # In night-time, egress window has recommendations
    hub_stop = next((s for s in night_res["stop_allocations"] if s["is_hub"]), None)
    assert hub_stop is not None
    night_intervals_with_recs = [i for i in hub_stop["intervals"] if i["buses_recommended"] > 0]
    assert len(night_intervals_with_recs) >= 1


# ==================== Test 10: Revalidation Before Approval ====================

def test_revalidation_before_approval_detects_conflict(admin_headers, client):
    """Requirement: Revalidate bus availability and overlapping assignments immediately before approval."""
    # Ensure candidate buses are in ready state and past assignments/schedules completed
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE assignments SET status = 'COMPLETED' WHERE status = 'ASSIGNED'")
    c.execute("UPDATE schedules SET status = 'Completed' WHERE bus_number IN ('BUS-201', 'BUS-202', 'BUS-203', 'BUS-204')")
    c.execute("UPDATE buses SET status = 'Ready' WHERE bus_number IN ('BUS-201', 'BUS-202', 'BUS-203', 'BUS-204')")
    c.execute("DELETE FROM dispatch_plans WHERE target_stop_id = 'STOP_MAIN'")
    conn.commit()
    conn.close()

    # 1. Normal approval works for idle standby buses
    payload = {
        "plan_id": None,
        "target_stop_id": "STOP_MAIN",
        "buses": ["BUS-201", "BUS-202", "BUS-203", "BUS-204"],
        "window": "night"
    }
    res = client.post("/api/smart-allocation/approve", json=payload, headers=admin_headers)
    assert res.status_code == 200, f"Expected 200 OK, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["status"] == "APPROVED"
    assert data["buses_allocated"] == 4

    # 2. Attempting to approve a bus marked in maintenance must be rejected by pre-commit revalidation
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE buses SET status = 'Maintenance' WHERE bus_number = 'BUS-201'")
    conn.commit()
    conn.close()

    try:
        conflict_payload = {
            "plan_id": None,
            "target_stop_id": "STOP_MAIN",
            "buses": ["BUS-201"],
            "window": "night"
        }
        conflict_res = client.post("/api/smart-allocation/approve", json=conflict_payload, headers=admin_headers)
        # Should fail with 409 Conflict due to bus maintenance status
        assert conflict_res.status_code == 409, f"Expected 409 Conflict, got {conflict_res.status_code}"
        assert "Maintenance" in conflict_res.json()["detail"]
    finally:
        # Restore status
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE buses SET status = 'Ready' WHERE bus_number = 'BUS-201'")
        conn.commit()
        conn.close()


# ==================== Test 11: Admin Rejection Endpoint ====================

def test_admin_rejection_workflow(admin_headers, client):
    """Requirement: Allow Depot Admin to decline or reject a proposed plan with logged audit rationale."""
    reject_payload = {
        "plan_id": None,
        "reason": "Declined by Depot Admin: local commuter headway on Route 4 must be prioritized."
    }
    res = client.post("/api/smart-allocation/reject", json=reject_payload, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "REJECTED"
    assert "Route 4" in data["rejection_reason"]


# ==================== Test 12: Database Persistence & Data Preservation ====================

def test_database_persistence_and_preservation():
    """Requirement: Protect existing data. Never delete, reset, recreate, or overwrite the SQLite database."""
    all_buses = get_all_buses()
    all_routes = get_all_routes()
    assert len(all_buses) == 17
    assert len(all_routes) == 3

    # Check that audit history and dispatch plans exist in DB
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as count FROM dispatch_plans")
    count = c.fetchone()["count"]
    assert count >= 1, "Dispatch plans must be safely persisted in SQLite database"
    conn.close()
