import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backend.analytics.etl import (
    clean_sensor_dataframe, 
    aggregate_daily_metrics, 
    compute_user_baseline
)
from backend.analytics.feature_engineering import (
    extract_time_series_features, 
    prepare_feature_matrix
)

def test_clean_sensor_dataframe():
    now = datetime.utcnow()
    raw_data = [
        {"timestamp": now, "heart_rate": 300.0, "steps": -5, "activity": "Sedentary", "spo2": 110.0, "temperature": 50.0},
        {"timestamp": now + timedelta(minutes=15), "heart_rate": None, "steps": 100, "activity": "Walking", "spo2": None, "temperature": 36.6},
        {"timestamp": now + timedelta(minutes=30), "heart_rate": 72.0, "steps": 0, "activity": "Sedentary", "spo2": 98.0, "temperature": 36.6},
    ]
    df = pd.DataFrame(raw_data)
    cleaned = clean_sensor_dataframe(df)

    assert len(cleaned) == 3
    # Check clipping
    assert cleaned.iloc[0]["heart_rate"] <= 220.0
    assert cleaned.iloc[0]["steps"] >= 0
    assert cleaned.iloc[0]["spo2"] <= 100.0
    assert cleaned.iloc[0]["temperature"] <= 42.5
    # Check forward fill on missing
    assert not pd.isna(cleaned.iloc[1]["heart_rate"])
    # Check is_resting logic
    assert cleaned.iloc[2]["is_resting"] == True
    assert cleaned.iloc[1]["is_resting"] == False

def test_aggregate_daily_metrics():
    now = datetime.utcnow()
    readings = []
    # 2 days of readings
    for day in range(2):
        for h in range(4):
            readings.append({
                "timestamp": now + timedelta(days=day, hours=h),
                "heart_rate": 70.0 + h * 5,
                "steps": 500,
                "activity": "Sedentary" if h == 0 else "Walking",
                "sleep_hours": 7.0,
                "spo2": 98.0,
                "temperature": 36.6,
                "is_resting": (h == 0)
            })
    df = pd.DataFrame(readings)
    daily = aggregate_daily_metrics(df)

    assert len(daily) == 2
    assert "resting_hr" in daily.columns
    assert "total_steps" in daily.columns
    assert daily.iloc[0]["total_steps"] == 2000

def test_compute_user_baseline():
    daily_rows = [
        {"date": datetime.utcnow().date() - timedelta(days=i), "resting_hr": 68.0 + i % 2, "total_steps": 8000, "total_sleep": 7.5, "min_spo2": 96.0, "avg_temp": 36.6}
        for i in range(7)
    ]
    daily_df = pd.DataFrame(daily_rows)
    baseline = compute_user_baseline(daily_df)

    assert "resting_hr_mean" in baseline
    assert 65.0 <= baseline["resting_hr_mean"] <= 75.0
    assert baseline["avg_daily_steps"] == 8000
    assert baseline["normal_spo2_min"] == 96.0

def test_feature_engineering():
    now = datetime.utcnow()
    readings = [
        {"timestamp": now + timedelta(minutes=i*15), "heart_rate": 70.0 + (i%3)*5, "steps": 0, "activity": "Sedentary", "sleep_hours": 7.0, "spo2": 98.0, "temperature": 36.6}
        for i in range(10)
    ]
    df = clean_sensor_dataframe(pd.DataFrame(readings))
    baseline = {"resting_hr_mean": 70.0, "resting_hr_std": 5.0, "normal_spo2_min": 95.0, "normal_temp_mean": 36.6}
    
    features_df = extract_time_series_features(df, baseline)
    assert "hr_zscore" in features_df.columns
    assert "hrv_rmssd_proxy" in features_df.columns
    assert "spo2_drop" in features_df.columns

    X = prepare_feature_matrix(features_df)
    assert X.shape[0] == 10
    assert X.shape[1] == 11
