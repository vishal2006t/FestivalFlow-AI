"""Tests for Camera Monitoring, Crowd Detection, Temporal Smoothing, and Privacy Compliance."""

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


def test_list_cameras():
    """Verify configured camera endpoints are returned with stop mappings."""
    token = get_admin_token()
    res = client.get("/api/cameras", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    cameras = res.json()
    assert len(cameras) >= 2

    cam_ids = [c["camera_id"] for c in cameras]
    assert "CAM-MAIN-01" in cam_ids
    assert "CAM-NORTH-01" in cam_ids

    main_cam = next(c for c in cameras if c["camera_id"] == "CAM-MAIN-01")
    assert main_cam["stop_id"] == "STOP_MAIN"
    assert main_cam["status"] == "CONNECTED"


def test_update_camera_configuration():
    """Depot Admin can update camera source type and ROI coordinates."""
    token = get_admin_token()
    update_payload = {
        "source_type": "rtsp",
        "stream_url": "rtsp://cctv.local/bay1_hd",
        "roi_x1": 0.20,
        "roi_y1": 0.30,
        "roi_x2": 0.80,
        "roi_y2": 0.75
    }
    res = client.put("/api/cameras/CAM-MAIN-01", json=update_payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] == "rtsp"
    assert data["stream_url"] == "rtsp://cctv.local/bay1_hd"
    assert data["roi_x1"] == 0.20


def test_detect_frame_with_smoothing_and_provenance():
    """Camera detection performs temporal smoothing and outputs explicit data provenance."""
    token = get_admin_token()
    detect_payload = {
        "source_type": "demo",
        "roi": [0.15, 0.25, 0.85, 0.85]
    }
    res = client.post("/api/cameras/CAM-MAIN-01/detect-frame", json=detect_payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()

    assert data["camera_id"] == "CAM-MAIN-01"
    assert data["status"] == "CONNECTED"
    assert "DEMO" in data["provenance"]
    assert data["people_count_smoothed"] > 0
    assert data["confidence_pct"] >= 70.0
    assert data["crowd_level"] in ["Low", "Moderate", "High", "Critical"]
    assert "temporal_smoothing" in data
    assert data["temporal_smoothing"]["algorithm"] == "Exponential Moving Average (EMA)"


def test_privacy_compliance_guarantees():
    """System transparently verifies zero facial recognition or biometric profiling."""
    token = get_admin_token()
    res = client.post("/api/cameras/CAM-MAIN-01/detect-frame", json={"source_type": "demo"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()

    privacy = data["privacy_compliance"]
    assert privacy["facial_recognition"] == "DISABLED"
    assert privacy["biometric_profiling"] == "NONE"
    assert privacy["identity_tracking"] == "ANONYMOUS_AGGREGATE_ONLY"

    for sample in data["detection_samples"]:
        assert "Person (Anonymized)" in sample["label"]
        assert "confidence" in sample
        assert len(sample["box"]) == 4


def test_crowd_readings_trend_history():
    """Historical crowd density readings are logged and accessible for trend curves."""
    token = get_admin_token()

    # Trigger detection
    client.post("/api/cameras/CAM-MAIN-01/detect-frame", json={"source_type": "demo"}, headers={"Authorization": f"Bearer {token}"})

    res = client.get("/api/crowd/readings?stop_id=STOP_MAIN", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    readings = res.json()
    assert len(readings) >= 1
    assert readings[-1]["stop_id"] == "STOP_MAIN"
    assert "smoothed_count" in readings[-1]
