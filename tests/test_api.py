"""Integration tests for FestivalFlow AI API endpoints."""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify GET / returns application information."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "FestivalFlow AI"
    assert data["status"] == "Operational"
    assert "endpoints" in data
    assert len(data["endpoints"]) >= 5


def test_health_endpoint():
    """Verify GET /health returns OK status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OK"
    assert data["service"] == "FestivalFlow AI"


def test_dashboard_endpoint():
    """Verify GET /dashboard returns HTML dashboard."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "FestivalFlow AI" in response.text
    assert "<!DOCTYPE html>" in response.text



def test_stops_endpoint():
    """Verify GET /api/stops returns Main Stand and Nearby Stop."""
    response = client.get("/api/stops")
    assert response.status_code == 200
    stops = response.json()
    assert len(stops) == 2
    stop_ids = [s["stop_id"] for s in stops]
    assert "STOP_MAIN" in stop_ids
    assert "STOP_NEARBY" in stop_ids

    main_stop = next(s for s in stops if s["stop_id"] == "STOP_MAIN")
    assert main_stop["current_scheduled_buses"] == 12

    nearby_stop = next(s for s in stops if s["stop_id"] == "STOP_NEARBY")
    assert nearby_stop["idle_buses"] == 4
    assert nearby_stop["min_service_buses"] == 1


def test_demand_endpoint_default():
    """Verify GET /api/demand returns 15-minute intervals and explainable metadata."""
    response = client.get("/api/demand")
    assert response.status_code == 200
    data = response.json()
    assert data["is_ml_model"] is False  # Transparently acknowledges baseline model
    assert "RuleBased" in data["model_type"]
    assert len(data["intervals"]) == 14
    assert "STOP_MAIN" in data["predictions"]
    assert "STOP_NEARBY" in data["predictions"]
    assert len(data["predictions"]["STOP_MAIN"]) == len(data["intervals"])


def test_demand_endpoint_weather_variation():
    """Verify weather modifies predicted surge intensity."""
    clear_res = client.get("/api/demand?weather=Clear").json()
    rain_res = client.get("/api/demand?weather=Heavy Rain").json()

    clear_peak = max(clear_res["predictions"]["STOP_MAIN"])
    rain_peak = max(rain_res["predictions"]["STOP_MAIN"])

    # Heavy rain compresses and magnifies peak crowd arrival
    assert rain_peak > clear_peak


def test_optimize_endpoint_default():
    """Verify POST /api/optimize returns valid reallocations and conserved fleet."""
    response = client.post("/api/optimize", json={})
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "OPTIMAL_FEASIBLE"
    assert data["fleet_conservation"]["is_conserved"] is True
    assert len(data["reallocations"]) > 0

    realloc = data["reallocations"][0]
    assert realloc["source_stop_id"] == "STOP_NEARBY"
    assert realloc["destination_stop_id"] == "STOP_MAIN"
    assert realloc["buses_moved"] > 0
    assert "recommended_departure_time" in realloc
    assert "source_impact" in realloc


def test_optimize_validation_error():
    """Verify proper validation response when invalid data is submitted."""
    response = client.post("/api/optimize", json={"stops": []})
    assert response.status_code == 422


def test_optimize_endpoint_partial_weather():
    """Verify frontend partial payload format with weather condition update."""
    payload = {
        "festival": {
            "weather_forecast": {"condition": "Light Rain"}
        }
    }
    response = client.post("/api/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPTIMAL_FEASIBLE"
    assert data["fleet_conservation"]["is_conserved"] is True

