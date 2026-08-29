import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple
from datetime import datetime

def clean_sensor_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans raw sensor data:
    1. Standardizes timestamps and sorts chronologically.
    2. Drops exact duplicates.
    3. Handles missing values via forward-fill and sensible defaults.
    4. Replaces impossible physiological extremes (outlier capping).
    5. Flags resting intervals (low activity + zero steps).
    """
    if df.empty:
        return df

    df = df.copy()

    # 1. Parse timestamps
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        df = df.drop_duplicates(subset=["timestamp"], keep="last")

    # 2. Physiological bounding/clipping
    if "heart_rate" in df.columns:
        df["heart_rate"] = pd.to_numeric(df["heart_rate"], errors="coerce")
        df["heart_rate"] = df["heart_rate"].clip(lower=35.0, upper=220.0)

    if "spo2" in df.columns:
        df["spo2"] = pd.to_numeric(df["spo2"], errors="coerce")
        df["spo2"] = df["spo2"].clip(lower=65.0, upper=100.0)

    if "temperature" in df.columns:
        df["temperature"] = pd.to_numeric(df["temperature"], errors="coerce")
        df["temperature"] = df["temperature"].clip(lower=34.0, upper=42.5)

    if "steps" in df.columns:
        df["steps"] = pd.to_numeric(df["steps"], errors="coerce").fillna(0).astype(int)
        df["steps"] = df["steps"].clip(lower=0, upper=5000)  # max per 5-15 min window

    if "sleep_hours" in df.columns:
        df["sleep_hours"] = pd.to_numeric(df["sleep_hours"], errors="coerce").fillna(0.0)
        df["sleep_hours"] = df["sleep_hours"].clip(lower=0.0, upper=24.0)

    if "activity" not in df.columns:
        df["activity"] = "Sedentary"
    else:
        df["activity"] = df["activity"].fillna("Sedentary")

    # 3. Handle missing values
    df["heart_rate"] = df["heart_rate"].ffill().bfill().fillna(72.0)
    df["spo2"] = df["spo2"].ffill().bfill().fillna(98.0)
    df["temperature"] = df["temperature"].ffill().bfill().fillna(36.6)

    # 4. Identify Resting periods (Sedentary or Sleeping with 0 steps)
    if "is_resting" not in df.columns:
        df["is_resting"] = (
            (df["steps"] == 0) & 
            (df["activity"].isin(["Sedentary", "Sleeping", "Resting"]))
        )

    return df

def aggregate_daily_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rolls up high-frequency sensor readings into daily health summaries:
    - Resting Heart Rate (mean HR during resting periods)
    - Average, Min, Max Heart Rate
    - Total Daily Steps
    - Total Sleep Duration
    - Average & Minimum SpO2
    - Average Body Temperature
    """
    if df.empty or "timestamp" not in df.columns:
        return pd.DataFrame()

    df = clean_sensor_dataframe(df)
    df["date"] = df["timestamp"].dt.date

    daily_rows = []
    for date_val, group in df.groupby("date"):
        resting_subset = group[group["is_resting"] == True]
        resting_hr = (
            resting_subset["heart_rate"].mean() 
            if not resting_subset.empty 
            else group["heart_rate"].quantile(0.2)
        )

        daily_rows.append({
            "date": date_val,
            "resting_hr": round(float(resting_hr), 1) if not pd.isna(resting_hr) else 70.0,
            "avg_hr": round(float(group["heart_rate"].mean()), 1),
            "min_hr": round(float(group["heart_rate"].min()), 1),
            "max_hr": round(float(group["heart_rate"].max()), 1),
            "total_steps": int(group["steps"].sum()),
            "total_sleep": round(float(group["sleep_hours"].max() if group["sleep_hours"].max() > 0 else group["sleep_hours"].sum()), 1),
            "avg_spo2": round(float(group["spo2"].mean()), 1),
            "min_spo2": round(float(group["spo2"].min()), 1),
            "avg_temp": round(float(group["temperature"].mean()), 2)
        })

    daily_df = pd.DataFrame(daily_rows)
    return daily_df.sort_values("date").reset_index(drop=True)

def compute_user_baseline(daily_df: pd.DataFrame, window_days: int = 7) -> Dict[str, Any]:
    """
    Calculates moving personal baseline metrics from historical daily records.
    """
    if daily_df.empty or len(daily_df) < 2:
        return {
            "resting_hr_mean": 70.0,
            "resting_hr_std": 5.5,
            "avg_daily_steps": 8000,
            "avg_sleep_hours": 7.5,
            "normal_spo2_min": 95.0,
            "normal_temp_mean": 36.6
        }

    tail_df = daily_df.tail(window_days)
    
    r_mean = float(tail_df["resting_hr"].mean())
    r_std = float(tail_df["resting_hr"].std())
    if pd.isna(r_std) or r_std < 1.0:
        r_std = 5.0

    steps_mean = int(tail_df["total_steps"].mean())
    sleep_mean = float(tail_df["total_sleep"].mean())
    spo2_min = float(tail_df["min_spo2"].mean())
    temp_mean = float(tail_df["avg_temp"].mean())

    return {
        "resting_hr_mean": round(r_mean, 1),
        "resting_hr_std": round(r_std, 1),
        "avg_daily_steps": max(1000, steps_mean),
        "avg_sleep_hours": round(max(3.0, sleep_mean), 1),
        "normal_spo2_min": round(max(90.0, spo2_min), 1),
        "normal_temp_mean": round(temp_mean, 2)
    }
