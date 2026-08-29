import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from backend.analytics.etl import clean_sensor_dataframe
from backend.analytics.feature_engineering import extract_time_series_features
from backend.models.anomaly_detector import AnomalyDetector
from backend.models.risk_classifier import HealthRiskClassifier

@pytest.fixture
def baseline_fixture():
    return {
        "resting_hr_mean": 70.0,
        "resting_hr_std": 6.0,
        "avg_daily_steps": 8000,
        "avg_sleep_hours": 7.5,
        "normal_spo2_min": 95.0,
        "normal_temp_mean": 36.6
    }

def test_rule_based_tachycardia_detection(baseline_fixture):
    detector = AnomalyDetector()
    readings = [
        {
            "timestamp": datetime.now(timezone.utc),
            "heart_rate": 115.0,  # Elevated resting HR (> 70 + 2.5*6 = 85)
            "steps": 0,
            "activity": "Sedentary",
            "sleep_hours": 7.0,
            "spo2": 98.0,
            "temperature": 36.6,
            "is_resting": True
        }
    ]
    df = pd.DataFrame(readings)
    alerts = detector.detect_rule_based_anomalies(df, baseline_fixture)

    assert len(alerts) >= 1
    hr_alerts = [a for a in alerts if a["parameter"] == "Heart Rate"]
    assert len(hr_alerts) == 1
    assert hr_alerts[0]["severity"] == "severe"

def test_rule_based_hypoxia_detection(baseline_fixture):
    detector = AnomalyDetector()
    readings = [
        {
            "timestamp": datetime.now(timezone.utc),
            "heart_rate": 75.0,
            "steps": 0,
            "activity": "Sedentary",
            "sleep_hours": 7.0,
            "spo2": 88.0,  # Severe Hypoxia (<90%)
            "temperature": 36.6,
            "is_resting": True
        }
    ]
    df = pd.DataFrame(readings)
    alerts = detector.detect_rule_based_anomalies(df, baseline_fixture)

    spo2_alerts = [a for a in alerts if a["parameter"] == "SpO2"]
    assert len(spo2_alerts) == 1
    assert spo2_alerts[0]["severity"] == "severe"

def test_rule_based_fever_detection(baseline_fixture):
    detector = AnomalyDetector()
    readings = [
        {
            "timestamp": datetime.now(timezone.utc),
            "heart_rate": 95.0,
            "steps": 0,
            "activity": "Sedentary",
            "sleep_hours": 4.0,
            "spo2": 97.0,
            "temperature": 38.9,  # High fever
            "is_resting": True
        }
    ]
    df = pd.DataFrame(readings)
    alerts = detector.detect_rule_based_anomalies(df, baseline_fixture)

    temp_alerts = [a for a in alerts if a["parameter"] == "Temperature"]
    assert len(temp_alerts) == 1
    assert temp_alerts[0]["severity"] == "severe"

def test_isolation_forest_ml_detection(baseline_fixture):
    detector = AnomalyDetector(contamination=0.08)
    
    # Generate 40 normal readings with distinct timestamps + 2 extreme anomalies
    readings = []
    base_time = datetime.now(timezone.utc) - timedelta(hours=24)
    for i in range(40):
        readings.append({
            "timestamp": base_time + timedelta(minutes=i * 30),
            "heart_rate": float(70.0 + np.random.normal(0, 2)),
            "steps": 0,
            "activity": "Sedentary",
            "sleep_hours": 7.5,
            "spo2": 98.0,
            "temperature": 36.6,
            "is_resting": True
        })
    # Add severe outlier
    readings.append({
        "timestamp": base_time + timedelta(minutes=41 * 30),
        "heart_rate": 155.0,
        "steps": 0,
        "activity": "Sedentary",
        "sleep_hours": 2.0,
        "spo2": 82.0,
        "temperature": 39.8,
        "is_resting": True
    })

    df = clean_sensor_dataframe(pd.DataFrame(readings))
    assert len(df) == 41
    df_features = extract_time_series_features(df, baseline_fixture)
    
    ml_alerts = detector.detect_ml_anomalies(df_features, baseline_fixture)
    assert len(ml_alerts) >= 1
    assert any(a["detector_type"] == "isolation_forest_ml" for a in ml_alerts)

def test_health_risk_classifier(baseline_fixture):
    classifier = HealthRiskClassifier()
    
    # 1. Normal state -> Low Risk
    normal_df = clean_sensor_dataframe(pd.DataFrame([{
        "timestamp": datetime.now(timezone.utc),
        "heart_rate": 70.0,
        "steps": 8000,
        "activity": "Walking",
        "sleep_hours": 7.5,
        "spo2": 98.5,
        "temperature": 36.6,
        "is_resting": False
    }]))
    normal_feats = extract_time_series_features(normal_df, baseline_fixture)
    normal_risk = classifier.assess_risk(normal_feats, baseline_fixture)
    assert normal_risk["overall_risk_level"] in ["Low", "Moderate"]
    assert normal_risk["risk_score_numeric"] < 50.0

    # 2. Critical state (High fever + hypoxia + tachycardia) -> High Risk
    acute_df = clean_sensor_dataframe(pd.DataFrame([{
        "timestamp": datetime.now(timezone.utc),
        "heart_rate": 130.0,
        "steps": 50,
        "activity": "Sedentary",
        "sleep_hours": 3.0,
        "spo2": 87.0,
        "temperature": 39.2,
        "is_resting": True
    }]))
    acute_feats = extract_time_series_features(acute_df, baseline_fixture)
    acute_risk = classifier.assess_risk(acute_feats, baseline_fixture)
    assert acute_risk["overall_risk_level"] == "High"
    assert acute_risk["risk_score_numeric"] >= 65.0
    assert len(acute_risk["risk_factors"]) >= 1
