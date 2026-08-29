import pandas as pd
import numpy as np
from typing import Dict, Any, List

def extract_time_series_features(df: pd.DataFrame, baseline: Dict[str, Any]) -> pd.DataFrame:
    """
    Computes time-series and rolling statistical features from raw/cleaned sensor readings:
    - hr_rolling_mean, hr_rolling_std (HRV proxy)
    - hr_resting_zscore: how many standard deviations current resting HR is from personal mean
    - elevated_sedentary_ratio: flag for high HR despite zero physical movement (stress/fever/arrhythmia)
    - spo2_deficit: distance below healthy 95% floor
    - temp_deviation: body temperature change from baseline
    - sleep_deficit_ratio: deviation from target sleep
    - step_deficit_ratio: daily activity deviation
    """
    if df.empty:
        return pd.DataFrame()

    df = df.copy().sort_values("timestamp").reset_index(drop=True)

    base_hr_mean = baseline.get("resting_hr_mean", 70.0)
    base_hr_std = baseline.get("resting_hr_std", 6.0)
    base_spo2_min = baseline.get("normal_spo2_min", 95.0)
    base_temp_mean = baseline.get("normal_temp_mean", 36.6)
    base_sleep = baseline.get("avg_sleep_hours", 7.5)
    base_steps = baseline.get("avg_daily_steps", 8000)

    # 1. Rolling statistics (short 6-sample window)
    window = min(6, len(df))
    df["hr_rolling_mean"] = df["heart_rate"].rolling(window=window, min_periods=1).mean()
    df["hr_rolling_std"] = df["heart_rate"].rolling(window=window, min_periods=1).std().fillna(2.0)

    # 2. HRV proxy (Successive difference / Root mean square of successive differences)
    df["hr_diff"] = df["heart_rate"].diff().abs().fillna(0.0)
    df["hrv_rmssd_proxy"] = df["hr_diff"].rolling(window=window, min_periods=1).apply(
        lambda x: np.sqrt(np.mean(x**2)) if len(x) > 0 else 2.0, raw=False
    ).fillna(2.0)

    # 3. Z-scores relative to personal baseline
    df["hr_zscore"] = (df["heart_rate"] - base_hr_mean) / max(1.0, base_hr_std)
    df["temp_diff"] = df["temperature"] - base_temp_mean
    
    # 4. Elevated HR during sedentary periods (e.g. HR > 85 while steps == 0)
    df["is_elevated_sedentary"] = (
        (df["steps"] == 0) & 
        (df["activity"].isin(["Sedentary", "Sleeping", "Resting"])) & 
        (df["heart_rate"] > (base_hr_mean + 1.5 * base_hr_std))
    ).astype(int)

    # 5. SpO2 desaturation severity
    df["spo2_drop"] = (base_spo2_min - df["spo2"]).clip(lower=0.0)

    # 6. Sleep & Activity deficits
    df["sleep_deficit"] = (base_sleep - df["sleep_hours"]).clip(lower=0.0)

    return df

FEATURE_COLUMNS = [
    "heart_rate",
    "hr_rolling_std",
    "hrv_rmssd_proxy",
    "hr_zscore",
    "steps",
    "sleep_hours",
    "spo2",
    "spo2_drop",
    "temperature",
    "temp_diff",
    "is_elevated_sedentary"
]

def prepare_feature_matrix(df_features: pd.DataFrame) -> np.ndarray:
    """
    Extracts the numeric feature matrix for ML models.
    """
    for col in FEATURE_COLUMNS:
        if col not in df_features.columns:
            df_features[col] = 0.0
    
    X = df_features[FEATURE_COLUMNS].fillna(0.0).values
    return X
