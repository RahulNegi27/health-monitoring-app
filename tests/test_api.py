import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_get_summary_endpoint():
    response = client.get("/api/health/summary")
    assert response.status_code == 200
    data = response.json()
    assert "heart_rate" in data
    assert "steps" in data
    assert "sleep" in data
    assert "spo2" in data
    assert "temperature" in data

def test_get_risk_score_endpoint():
    response = client.get("/api/health/risk-score")
    assert response.status_code == 200
    data = response.json()
    assert "overall_risk_level" in data
    assert "risk_score_numeric" in data
    assert "primary_concerns" in data

def test_get_trends_endpoint():
    response = client.get("/api/health/trends?days=7")
    assert response.status_code == 200
    data = response.json()
    assert "baseline" in data
    assert "daily_trends" in data
    assert "timeline" in data

def test_generate_scenario_endpoint():
    payload = {"scenario": "fever", "days": 7}
    response = client.post("/api/simulator/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["scenario"] == "fever"

def test_ingest_reading_endpoint():
    payload = {
        "heart_rate": 78.0,
        "steps": 120,
        "activity": "Walking",
        "sleep_hours": 7.2,
        "spo2": 98.5,
        "temperature": 36.6,
        "is_resting": False
    }
    response = client.post("/api/health/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["ingested_count"] == 1

def test_user_profile_endpoints():
    # 1. Get profile
    res1 = client.get("/api/user/profile")
    assert res1.status_code == 200
    assert "resting_hr_mean" in res1.json()

    # 2. Update profile
    update_payload = {
        "resting_hr_mean": 68.0,
        "target_steps": 10000
    }
    res2 = client.put("/api/user/profile", json=update_payload)
    assert res2.status_code == 200
    updated = res2.json()
    assert updated["resting_hr_mean"] == 68.0
    assert updated["target_steps"] == 10000
