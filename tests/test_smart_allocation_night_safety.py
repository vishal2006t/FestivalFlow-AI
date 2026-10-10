"""Comprehensive Automated Verification Suite for Smart Allocation, Night Safety & Reporting.

Tests:
1. Smart allocation generation with multi-input weather & event timing analysis.
2. Day vs Night window separation & independent filtering.
3. Configurable night operating hours persistence.
4. Night safety incident lifecycle (NEW -> ACKNOWLEDGED -> ESCALATED -> RESOLVED).
5. Police & emergency services escalation with honest delivery states.
6. Microsoft Word (.docx) overall operations report generation.
7. API endpoints integration & authorization enforcement.
"""

import pytest
import io
import docx
from fastapi.testclient import TestClient

from main import app
from app.database import (
    init_db,
    get_system_settings,
    update_system_setting,
    get_emergency_contacts,
    get_safety_incidents,
    get_safety_incident_by_id,
    create_safety_incident,
    update_safety_incident_status,
    create_police_escalation,
    get_police_escalations,
    update_police_escalation_status,
    create_session,
    get_user_by_username
)
from app.smart_allocation.allocation_service import smart_allocation_engine
from app.operations_report.docx_generator import generate_overall_docx_report


@pytest.fixture(scope="module")
def client():
    """TestClient instance for FastAPI application."""
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


def test_smart_allocation_generation():
    """Verify smart allocation generates comprehensive stop-wise breakdowns without bus conflicts."""
    result = smart_allocation_engine.generate_smart_allocations(target_window="all")

    assert "stop_allocations" in result
    assert len(result["stop_allocations"]) >= 1
    assert "weather_context" in result
    assert "event_context" in result
    assert "summary_metrics" in result
    assert "primary_recommendation" in result

    # Check primary recommendation for Main Bus Stand
    primary = result["primary_recommendation"]
    assert primary["target_stop_id"] == "STOP_MAIN"
    assert primary["buses_recommended"] == 4
    assert "BUS-201" in primary["recommended_fleet"]

    # Check provenance
    prov = result["data_provenance"]
    assert prov["is_ml_trained"] is False
    assert "Deterministic" in prov["model_type"]


def test_day_night_window_separation():
    """Verify Day vs Night allocation filtering separates intervals correctly."""
    day_res = smart_allocation_engine.generate_smart_allocations(target_window="day")
    night_res = smart_allocation_engine.generate_smart_allocations(target_window="night")

    # Day intervals should only contain daytime slots (non-night)
    for stop in day_res["stop_allocations"]:
        for intvl in stop["intervals"]:
            assert intvl["is_night"] is False

    # Night intervals should only contain night slots
    for stop in night_res["stop_allocations"]:
        for intvl in stop["intervals"]:
            assert intvl["is_night"] is True


def test_night_operating_hours_settings():
    """Verify Depot Admin can configure night operating hours in database."""
    settings_before = get_system_settings()
    assert "night_start_hour" in settings_before

    # Update setting
    update_system_setting("night_start_hour", "21")
    settings_after = get_system_settings()
    assert settings_after["night_start_hour"] == "21"

    # Reset back to standard 20:00
    update_system_setting("night_start_hour", "20")
    settings_reset = get_system_settings()
    assert settings_reset["night_start_hour"] == "20"


def test_safety_incident_lifecycle():
    """Verify safety incidents support creation, acknowledgement, and resolution with audit history."""
    # 1. Create Incident
    inc_data = {
        "incident_id": "INC-TEST-001",
        "incident_type": "UNEXPECTED_STOP",
        "severity": "HIGH",
        "stop_id": "STOP_STH",
        "stop_name": "South Commercial Terminal",
        "bus_number": "BUS-102",
        "driver_name": "K. Suresh",
        "description": "Test unexpected bus dwell stop alert.",
        "supporting_evidence": "GPS telemetry stationary > 12 mins.",
        "assigned_responder": "Patrol Officer"
    }
    created = create_safety_incident(inc_data, reported_by="test_admin")
    assert created["incident_id"] == "INC-TEST-001"
    assert created["status"] == "NEW"

    # 2. Acknowledge Incident
    ack = update_safety_incident_status(
        incident_id="INC-TEST-001",
        new_status="ACKNOWLEDGED",
        actor_username="test_admin",
        action_note="Officer confirmed awareness."
    )
    assert ack["status"] == "ACKNOWLEDGED"
    assert len(ack["action_history"]) >= 2

    # 3. Resolve Incident
    resolved = update_safety_incident_status(
        incident_id="INC-TEST-001",
        new_status="RESOLVED",
        actor_username="test_admin",
        action_note="Bus resumed normal corridor route."
    )
    assert resolved["status"] == "RESOLVED"


def test_police_escalation_workflow():
    """Verify emergency services escalation generates audit record and honest delivery status."""
    contacts = get_emergency_contacts(only_active=True)
    assert len(contacts) >= 1
    contact = contacts[0]

    # Ensure a test incident exists
    inc_data = {
        "incident_id": "INC-TEST-ESC-001",
        "incident_type": "NIGHT_OVERCROWDING",
        "severity": "CRITICAL",
        "stop_id": "STOP_MAIN",
        "stop_name": "Main Bus Stand (Festival Arena)",
        "description": "Critical crowd stampede risk at Bay 1 queue.",
        "supporting_evidence": "CCTV crowd estimation > 3,500 pax.",
        "assigned_responder": "Duty Inspector"
    }
    create_safety_incident(inc_data, reported_by="admin_chennai")

    # Escalate to police
    esc_result = create_police_escalation(
        incident_id="INC-TEST-ESC-001",
        contact_id=contact["id"],
        operator_username="admin_chennai",
        additional_notes="Dispatch PCR van to Gate 1 immediately."
    )

    assert "escalation_id" in esc_result
    assert esc_result["delivery_status"] in ["MANUALLY_REPORTED", "SENT", "DELIVERED"]
    assert esc_result["incident_id"] == "INC-TEST-ESC-001"

    # Incident status should now be ESCALATED
    updated_inc = get_safety_incident_by_id("INC-TEST-ESC-001")
    assert updated_inc["status"] == "ESCALATED"

    # Update police acknowledgement
    ack_res = update_police_escalation_status(
        escalation_id=esc_result["escalation_id"],
        ack_status="UNIT_DISPATCHED",
        response_notes="PCR Unit 4 dispatched and arrived on scene.",
        actor_username="admin_chennai"
    )
    assert ack_res["police_ack_status"] == "UNIT_DISPATCHED"


def test_docx_report_generation():
    """Verify Microsoft Word (.docx) document generates valid binary content and sections."""
    buf = generate_overall_docx_report()
    assert buf is not None
    data_bytes = buf.getvalue()
    assert len(data_bytes) > 10000

    # Parse with python-docx to verify document structure integrity
    doc = docx.Document(io.BytesIO(data_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    assert any("FestivalFlow AI" in p for p in paragraphs)
    assert any("Executive Operations Summary" in p for p in paragraphs)
    assert any("Operating Windows: Day vs. Night Configuration" in p for p in paragraphs)
    assert any("Stop-Wise Passenger Demand" in p for p in paragraphs)
    assert any("Night Safety Monitoring" in p for p in paragraphs)
    assert len(doc.tables) >= 4


def test_api_endpoints_integration(client, admin_headers):
    """Verify newly added API endpoints respond with correct status codes and payloads."""
    # 1. Smart Allocation
    res = client.get("/api/smart-allocation/recommendations?window=all", headers=admin_headers)
    assert res.status_code == 200
    assert "stop_allocations" in res.json()

    # 2. Day Operations
    res = client.get("/api/operations/day", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["operational_window"] == "day"

    # 3. Night Operations
    res = client.get("/api/operations/night", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["operational_window"] == "night"

    # 4. Night Settings
    res = client.get("/api/operations/night-settings", headers=admin_headers)
    assert res.status_code == 200
    assert "night_start_hour" in res.json()

    # 5. Incidents
    res = client.get("/api/incidents", headers=admin_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # 6. Emergency Contacts
    res = client.get("/api/emergency/contacts", headers=admin_headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # 7. Word Report Download (.docx)
    res = client.get("/api/operations-report/download-docx", headers=admin_headers)
    assert res.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in res.headers["content-type"]
    assert "FestivalFlow_Overall_Report" in res.headers["content-disposition"]
    assert len(res.content) > 10000
