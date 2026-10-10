"""Comprehensive tests for Round 1 security hardening, multi-bus dispatch planning,
driver IDOR protection, safety escalations, and audit logging."""

import pytest
from fastapi.testclient import TestClient
from main import app
from app.database import (
    init_db,
    verify_password,
    get_user_by_username
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Reset to clean seeded state before each test."""
    init_db(force_reset=True)


def get_admin_token() -> str:
    res = client.post("/api/auth/login", json={
        "username": "admin_chennai",
        "password": "Admin@Depot2026",
        "role": "depot_admin"
    })
    assert res.status_code == 200
    return res.json()["token"]


def get_driver_token(username: str = "driver_ramesh") -> str:
    res = client.post("/api/auth/login", json={
        "username": username,
        "password": "Driver@2026",
        "role": "driver"
    })
    assert res.status_code == 200
    return res.json()["token"]


# ==================== 1. Password Hashing & Secret Exposure ====================

def test_password_stored_as_secure_hash():
    """Passwords must be hashed (bcrypt or secure hash) and not stored in plaintext."""
    user = get_user_by_username("admin_chennai")
    assert user is not None
    assert user["password_hash"] != "Admin@Depot2026"
    assert len(user["password_hash"]) > 20
    # Verifies hash matches
    assert verify_password("Admin@Depot2026", user["password_hash"], user["salt"]) is True
    assert verify_password("WrongPassword", user["password_hash"], user["salt"]) is False


def test_api_responses_never_expose_password_hashes():
    """User profile and list endpoints must never return password hashes or salts."""
    admin_token = get_admin_token()
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert "password" not in me_data
    assert "password_hash" not in me_data
    assert "salt" not in me_data


# ==================== 2. Admin vs Driver Object-Level Authorization ====================

def test_unauthenticated_requests_rejected():
    """Endpoints requiring authentication must return 401."""
    assert client.get("/api/schedules").status_code == 401
    assert client.get("/api/driver/my-schedules").status_code == 401
    assert client.get("/api/admin/summary").status_code == 401
    assert client.get("/api/audit-logs").status_code == 401
    assert client.get("/api/reports").status_code == 401


def test_driver_forbidden_from_admin_summary_and_audit():
    """Drivers cannot access admin KPI summary or security audit logs."""
    driver_token = get_driver_token("driver_ramesh")
    summary_res = client.get("/api/admin/summary", headers={"Authorization": f"Bearer {driver_token}"})
    assert summary_res.status_code == 403

    audit_res = client.get("/api/audit-logs", headers={"Authorization": f"Bearer {driver_token}"})
    assert audit_res.status_code == 403


def test_driver_cannot_update_another_drivers_schedule():
    """Object-level authorization: Driver cannot modify another driver's schedule."""
    # Driver Ramesh attempts to update Schedule #2 (assigned to Driver Suresh)
    ramesh_token = get_driver_token("driver_ramesh")
    patch_res = client.patch(
        "/api/driver/schedules/2/status",
        json={"status": "En Route"},
        headers={"Authorization": f"Bearer {ramesh_token}"}
    )
    assert patch_res.status_code == 403
    assert "Forbidden" in patch_res.json()["detail"]


def test_driver_cannot_read_another_drivers_notification():
    """Object-level authorization: Driver cannot acknowledge another driver's notification."""
    suresh_token = get_driver_token("driver_suresh")
    # Notification #1 is addressed to driver_ramesh (id 3)
    res = client.patch(
        "/api/driver/notifications/1/read",
        headers={"Authorization": f"Bearer {suresh_token}"}
    )
    assert res.status_code == 403


# ==================== 3. Driver Trip Status Transitions ====================

def test_driver_permitted_status_workflow():
    """Driver can transition schedule through Accepted -> En Route -> Arrived -> Boarding -> Completed."""
    ramesh_token = get_driver_token("driver_ramesh")

    # Permitted statuses
    for st in ["Accepted", "En Route", "Arrived", "Boarding", "Completed"]:
        res = client.patch(
            "/api/driver/schedules/1/status",
            json={"status": st},
            headers={"Authorization": f"Bearer {ramesh_token}"}
        )
        assert res.status_code == 200
        assert res.json()["status"] == st


def test_driver_cannot_set_disallowed_status():
    """Driver cannot set admin-only status like 'Cancelled' or arbitrary text."""
    ramesh_token = get_driver_token("driver_ramesh")
    res = client.patch(
        "/api/driver/schedules/1/status",
        json={"status": "Cancelled"},
        headers={"Authorization": f"Bearer {ramesh_token}"}
    )
    assert res.status_code in [400, 422]


# ==================== 4. Multi-Bus Redistribution & Transactional Approval ====================

def test_generate_and_approve_multi_bus_plan():
    """Admin can evaluate 4-bus evacuation plan, observe transparent candidates and unmet demand, and approve it."""
    admin_token = get_admin_token()

    # 1. Generate plan for 40,000 festival crowd scenario (requesting 4 buses)
    plan_res = client.post(
        "/api/dispatch/plan",
        json={
            "target_stop_id": "STOP_MAIN",
            "target_stop_name": "Main Bus Stand (Festival Arena)",
            "buses_requested": 4,
            "crowd_count": 400
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert plan_res.status_code in [200, 201]
    plan = plan_res.json()
    assert plan["target_stop_id"] == "STOP_MAIN"
    assert plan["buses_requested"] == 4
    assert plan["status"] == "PENDING"
    assert plan["buses_allocated"] >= 1
    # Explains unmet demand when less than 4 buses allocated
    if plan["buses_allocated"] < 4:
        assert plan["unmet_demand_reason"] is not None
        assert "unmet" in plan["unmet_demand_reason"].lower() or "minimum" in plan["unmet_demand_reason"].lower()

    # 2. Driver cannot approve plan
    driver_token = get_driver_token("driver_ramesh")
    drv_app = client.post(
        f"/api/dispatch/plans/{plan['id']}/approve",
        headers={"Authorization": f"Bearer {driver_token}"}
    )
    assert drv_app.status_code == 403

    # 3. Admin approves plan atomically
    app_res = client.post(
        f"/api/dispatch/plans/{plan['id']}/approve",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert app_res.status_code == 200
    app_data = app_res.json()
    assert app_data["status"] == "APPROVED"
    assert app_data["buses_assigned"] >= 1

    # 4. Attempting duplicate approval on already approved plan fails safely
    dup_res = client.post(
        f"/api/dispatch/plans/{plan['id']}/approve",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert dup_res.status_code == 400


def test_reject_multi_bus_plan():
    """Admin can reject a dispatch plan with reason, creating no assignments."""
    admin_token = get_admin_token()

    plan_res = client.post(
        "/api/dispatch/plan",
        json={
            "target_stop_id": "STOP_NORTH",
            "target_stop_name": "Tech Hub North Stop",
            "buses_requested": 2,
            "crowd_count": 120
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert plan_res.status_code in [200, 201]
    plan_id = plan_res.json()["id"]

    rej_res = client.post(
        f"/api/dispatch/plans/{plan_id}/reject",
        json={"reason": "Crowd queue clearing faster than projected."},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == "REJECTED"


# ==================== 5. Driver Incident Reports ====================

def test_driver_reports_delay_and_admin_resolves():
    """Driver logs an operational delay report; Admin reviews and resolves it."""
    driver_token = get_driver_token("driver_ramesh")

    # 1. Driver creates report
    create_res = client.post(
        "/api/driver/reports",
        json={
            "bus_number": "BUS-201",
            "report_type": "BREAKDOWN",
            "severity": "CRITICAL",
            "stop_name": "Tech Hub North Stop",
            "description": "Air brake pressure warning on BUS-201; immediate assistance requested."
        },
        headers={"Authorization": f"Bearer {driver_token}"}
    )
    assert create_res.status_code in [200, 201]
    rep = create_res.json()
    assert rep["report_type"] == "BREAKDOWN"
    assert rep["severity"] == "CRITICAL"

    # 2. Driver fetches their own reports
    my_reports = client.get("/api/driver/my-reports", headers={"Authorization": f"Bearer {driver_token}"}).json()
    assert any("Air brake pressure warning" in r["description"] for r in my_reports)

    # 3. Admin acknowledges and resolves report
    admin_token = get_admin_token()
    ack_res = client.patch(
        f"/api/reports/{rep['id']}/status",
        json={"status": "IN_REVIEW", "admin_response": "Dispatched maintenance team"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "IN_REVIEW"

    resolve_res = client.patch(
        f"/api/reports/{rep['id']}/status",
        json={"status": "RESOLVED", "admin_response": "Brake pressure restored and verified."},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "RESOLVED"


# ==================== 6. Safety Alert Escalation Workflow ====================

def test_safety_alert_escalation_workflow():
    """Depot Admin can escalate a late-night crowd safety alert to transport authorities."""
    admin_token = get_admin_token()

    esc_res = client.post(
        "/api/alerts/1/escalate",
        json={
            "escalation_action": "Central Transit Operations Control Escalation",
            "notes": "Late-night queue exceeded 22m with 142 attendees. Requesting standby relief fleet.",
            "requested_mutual_aid": False
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert esc_res.status_code == 200
    alert = esc_res.json()
    assert alert["status"] == "ESCALATED"
    assert "Central Transit Operations" in alert["recommended_action"]


# ==================== 7. Audit Log Sanitization ====================

def test_audit_logs_contain_no_passwords_or_tokens():
    """Audit logs must never log raw passwords, hashes, or authorization tokens."""
    admin_token = get_admin_token()
    logs_res = client.get("/api/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    assert logs_res.status_code == 200
    logs = logs_res.json()
    assert len(logs) > 0

    for entry in logs:
        detail = (entry.get("action_details") or "").lower()
        assert "admin@depot2026" not in detail
        assert "driver@2026" not in detail
        assert "bearer" not in detail


# ==================== 8. SSRF Camera Stream Protection ====================

def test_camera_stream_url_ssrf_blocked():
    """SSRF: Configuring camera with cloud metadata or arbitrary local IP is blocked."""
    admin_token = get_admin_token()
    bad_url_res = client.put(
        "/api/cameras/CAM-MAIN-01",
        json={
            "stream_url": "http://169.254.169.254/latest/meta-data/"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert bad_url_res.status_code in [400, 422]
