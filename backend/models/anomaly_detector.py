import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional
from sklearn.ensemble import IsolationForest
from backend.analytics.feature_engineering import (
    extract_time_series_features, 
    prepare_feature_matrix, 
    FEATURE_COLUMNS
)

class AnomalyDetector:
    def __init__(self, contamination: float = 0.05, random_state: int = 42):
        self.contamination = contamination
        self.random_state = random_state
        self.iso_forest = IsolationForest(
            contamination=self.contamination,
            random_state=self.random_state,
            n_estimators=100
        )
        self.is_fitted = False

    def fit_isolation_forest(self, df_features: pd.DataFrame):
        """
        Trains the unsupervised Isolation Forest on feature matrix.
        """
        if len(df_features) < 10:
            return
        X = prepare_feature_matrix(df_features)
        self.iso_forest.fit(X)
        self.is_fitted = True

    def detect_rule_based_anomalies(
        self, 
        df: pd.DataFrame, 
        baseline: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Phase 1: Rule-based & Dynamic Baseline Z-Score Detection.
        Evaluates readings against physiological bounds and personalized baseline thresholds.
        """
        alerts = []
        if df.empty:
            return alerts

        base_hr_mean = baseline.get("resting_hr_mean", 70.0)
        base_hr_std = baseline.get("resting_hr_std", 6.0)
        base_spo2_min = baseline.get("normal_spo2_min", 95.0)

        for _, row in df.iterrows():
            ts = row.get("timestamp")
            hr = float(row.get("heart_rate", 70.0))
            steps = int(row.get("steps", 0))
            activity = str(row.get("activity", "Sedentary"))
            spo2 = float(row.get("spo2", 98.0))
            temp = float(row.get("temperature", 36.6))
            sleep = float(row.get("sleep_hours", 0.0))
            is_resting = bool(row.get("is_resting", False))

            z_hr = (hr - base_hr_mean) / max(1.0, base_hr_std)

            # 1. Resting Tachycardia / Elevated Resting HR
            if is_resting and (hr > (base_hr_mean + 2.5 * base_hr_std) or hr >= 100):
                severity = "severe" if (hr >= 110 or z_hr >= 3.5) else "moderate"
                alerts.append({
                    "timestamp": ts,
                    "parameter": "Heart Rate",
                    "metric_value": hr,
                    "baseline_value": base_hr_mean,
                    "deviation_zscore": round(float(z_hr), 2),
                    "severity": severity,
                    "detector_type": "rule_based_baseline",
                    "explanation": f"Resting HR of {hr:.0f} BPM is significantly above your normal baseline of {base_hr_mean:.0f}±{base_hr_std:.0f} BPM (Z-Score: +{z_hr:.1f}σ).",
                    "recommendation": "Rest in a comfortable position, hydrate, avoid caffeine, and monitor if heart rate remains elevated."
                })

            # 2. Resting Bradycardia
            elif is_resting and hr < 48:
                alerts.append({
                    "timestamp": ts,
                    "parameter": "Heart Rate",
                    "metric_value": hr,
                    "baseline_value": base_hr_mean,
                    "deviation_zscore": round(float(z_hr), 2),
                    "severity": "moderate" if hr < 42 else "mild",
                    "detector_type": "rule_based_baseline",
                    "explanation": f"Resting HR of {hr:.0f} BPM is lower than standard resting limits.",
                    "recommendation": "If you experience dizziness, lightheadedness, or fatigue, consult a healthcare provider."
                })

            # 3. Acute SpO2 Desaturation
            if spo2 < 90.0:
                alerts.append({
                    "timestamp": ts,
                    "parameter": "SpO2",
                    "metric_value": spo2,
                    "baseline_value": base_spo2_min,
                    "deviation_zscore": round(float((98.0 - spo2) / 2.0), 2),
                    "severity": "severe",
                    "detector_type": "rule_based_clinical",
                    "explanation": f"Blood oxygen saturation dropped to {spo2:.1f}%, which is below the safe threshold of 90%.",
                    "recommendation": "Take deep breaths in an upright posture. If low readings persist or if you feel short of breath, seek immediate medical attention."
                })
            elif spo2 < base_spo2_min:
                alerts.append({
                    "timestamp": ts,
                    "parameter": "SpO2",
                    "metric_value": spo2,
                    "baseline_value": base_spo2_min,
                    "deviation_zscore": round(float((98.0 - spo2) / 2.0), 2),
                    "severity": "mild" if spo2 >= 93 else "moderate",
                    "detector_type": "rule_based_clinical",
                    "explanation": f"SpO2 reading of {spo2:.1f}% is lower than your typical baseline of {base_spo2_min:.0f}%.",
                    "recommendation": "Ensure sensor has snug contact with skin, sit upright, and recheck in a few minutes."
                })

            # 4. Elevated Body Temperature / Fever
            if temp >= 38.5:
                alerts.append({
                    "timestamp": ts,
                    "parameter": "Temperature",
                    "metric_value": temp,
                    "baseline_value": 36.6,
                    "deviation_zscore": round(float((temp - 36.6) / 0.4), 2),
                    "severity": "severe",
                    "detector_type": "rule_based_clinical",
                    "explanation": f"Body temperature of {temp:.1f}°C indicates a high fever.",
                    "recommendation": "Stay well hydrated, rest, monitor other symptoms, and consult a doctor if fever persists."
                })
            elif temp >= 37.8:
                alerts.append({
                    "timestamp": ts,
                    "parameter": "Temperature",
                    "metric_value": temp,
                    "baseline_value": 36.6,
                    "deviation_zscore": round(float((temp - 36.6) / 0.4), 2),
                    "severity": "moderate",
                    "detector_type": "rule_based_clinical",
                    "explanation": f"Elevated temperature of {temp:.1f}°C detected (mild fever).",
                    "recommendation": "Get adequate rest and fluids; monitor vital trends."
                })

            # 5. High HR during Sedentary State (Stress / Physiological strain)
            if steps == 0 and activity in ["Sedentary", "Resting"] and hr >= 95 and temp < 37.8:
                alerts.append({
                    "timestamp": ts,
                    "parameter": "Heart Rate / Activity Divergence",
                    "metric_value": hr,
                    "baseline_value": base_hr_mean,
                    "deviation_zscore": round(float(z_hr), 2),
                    "severity": "mild",
                    "detector_type": "hybrid_rule",
                    "explanation": f"Heart rate elevated to {hr:.0f} BPM during zero physical movement without fever.",
                    "recommendation": "Possible stress, caffeine surge, or dehydration. Try guided breathing exercises and relax."
                })

        return alerts

    def detect_ml_anomalies(
        self, 
        df_features: pd.DataFrame, 
        baseline: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Phase 2: Unsupervised Machine Learning Anomaly Detection using Isolation Forest.
        """
        ml_alerts = []
        if df_features.empty or len(df_features) < 8:
            return ml_alerts

        # Fit model on current batch if not fitted
        if not self.is_fitted or len(df_features) >= 20:
            self.fit_isolation_forest(df_features)

        if not self.is_fitted:
            return ml_alerts

        X = prepare_feature_matrix(df_features)
        predictions = self.iso_forest.predict(X)       # -1 for anomaly, 1 for normal
        decision_scores = self.iso_forest.decision_function(X) # lower score = more anomalous

        anom_indices = np.where(predictions == -1)[0]
        for idx in anom_indices:
            row = df_features.iloc[idx]
            raw_score = float(decision_scores[idx])
            # Normalized anomaly strength 0.0 to 1.0
            anomaly_strength = max(0.0, min(1.0, -raw_score * 3.0))

            # Determine dominant contributing factor
            hr_z = abs(row.get("hr_zscore", 0.0))
            spo2_d = row.get("spo2_drop", 0.0)
            temp_d = abs(row.get("temp_diff", 0.0))
            
            top_param = "Multivariate Anomaly"
            explanation = "Multivariate anomaly: combination of vitals deviates from normal historical clusters."
            
            if hr_z >= 2.0 and temp_d >= 0.8:
                top_param = "HR & Temperature Synergy"
                explanation = f"Concurrently elevated heart rate ({row['heart_rate']:.0f} BPM) and temperature ({row['temperature']:.1f}°C)."
            elif spo2_d >= 3.0:
                top_param = "SpO2 Pattern"
                explanation = f"Sub-optimal oxygen saturation ({row['spo2']:.1f}%) observed in multi-parameter cluster."
            elif hr_z >= 2.0:
                top_param = "Heart Rate Dynamics"
                explanation = f"Atypical heart rate pattern ({row['heart_rate']:.0f} BPM, HRV: {row['hrv_rmssd_proxy']:.1f})."

            ml_alerts.append({
                "timestamp": row.get("timestamp"),
                "parameter": top_param,
                "metric_value": float(row.get("heart_rate", 70.0)),
                "baseline_value": float(baseline.get("resting_hr_mean", 70.0)),
                "deviation_zscore": round(float(hr_z), 2),
                "severity": "moderate" if anomaly_strength > 0.4 else "mild",
                "detector_type": "isolation_forest_ml",
                "explanation": explanation,
                "recommendation": "Review current activity context and check for recurring symptoms."
            })

        return ml_alerts
