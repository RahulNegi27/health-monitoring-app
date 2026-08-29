import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple
from sklearn.ensemble import RandomForestClassifier
from backend.analytics.feature_engineering import prepare_feature_matrix, FEATURE_COLUMNS

class HealthRiskClassifier:
    """
    Supervised Machine Learning Risk Engine:
    Classifies multi-parameter health readings into Low, Moderate, or High Risk tiers
    and produces explainable feature contribution rankings.
    """
    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.model = RandomForestClassifier(
            n_estimators=100, 
            max_depth=6, 
            random_state=self.random_state
        )
        self.classes_ = ["Low", "Moderate", "High"]
        self.is_trained = False
        self._bootstrap_initial_training()

    def _generate_synthetic_training_corpus(self, n_samples: int = 1500) -> Tuple[np.ndarray, np.ndarray]:
        """
        Synthesizes a clinically grounded training dataset across physiological feature space.
        """
        np.random.seed(self.random_state)
        
        # 1. Normal / Low Risk samples (approx 60%)
        n_low = int(n_samples * 0.6)
        hr_low = np.random.normal(70, 5, n_low).clip(55, 85)
        hr_std_low = np.random.uniform(1.5, 4.0, n_low)
        hrv_low = np.random.uniform(25.0, 55.0, n_low)
        hr_z_low = (hr_low - 70.0) / 6.0
        steps_low = np.random.randint(4000, 12000, n_low)
        sleep_low = np.random.uniform(6.5, 9.0, n_low)
        spo2_low = np.random.uniform(96.0, 99.5, n_low)
        spo2_drop_low = np.zeros(n_low)
        temp_low = np.random.normal(36.6, 0.2, n_low).clip(36.2, 37.1)
        temp_diff_low = temp_low - 36.6
        elev_sed_low = np.zeros(n_low)
        
        X_low = np.column_stack([
            hr_low, hr_std_low, hrv_low, hr_z_low, steps_low, sleep_low,
            spo2_low, spo2_drop_low, temp_low, temp_diff_low, elev_sed_low
        ])
        y_low = np.zeros(n_low, dtype=int)  # 0 = Low

        # 2. Moderate Risk samples (approx 25%) - Stress, mild fever, fatigue, borderline SpO2
        n_mod = int(n_samples * 0.25)
        hr_mod = np.random.normal(86, 6, n_mod).clip(78, 102)
        hr_std_mod = np.random.uniform(3.5, 8.0, n_mod)
        hrv_mod = np.random.uniform(12.0, 28.0, n_mod)
        hr_z_mod = (hr_mod - 70.0) / 6.0
        steps_mod = np.random.randint(1500, 5000, n_mod)
        sleep_mod = np.random.uniform(4.5, 6.2, n_mod)
        spo2_mod = np.random.uniform(93.0, 95.8, n_mod)
        spo2_drop_mod = (95.0 - spo2_mod).clip(min=0)
        temp_mod = np.random.normal(37.5, 0.3, n_mod).clip(37.2, 38.0)
        temp_diff_mod = temp_mod - 36.6
        elev_sed_mod = np.random.choice([0, 1], size=n_mod, p=[0.4, 0.6])

        X_mod = np.column_stack([
            hr_mod, hr_std_mod, hrv_mod, hr_z_mod, steps_mod, sleep_mod,
            spo2_mod, spo2_drop_mod, temp_mod, temp_diff_mod, elev_sed_mod
        ])
        y_mod = np.ones(n_mod, dtype=int)   # 1 = Moderate

        # 3. High Risk samples (approx 15%) - High fever, acute desaturation, severe tachycardia
        n_high = n_samples - n_low - n_mod
        hr_high = np.random.normal(112, 12, n_high).clip(98, 150)
        hr_std_high = np.random.uniform(6.0, 14.0, n_high)
        hrv_high = np.random.uniform(5.0, 16.0, n_high)
        hr_z_high = (hr_high - 70.0) / 6.0
        steps_high = np.random.randint(200, 2500, n_high)
        sleep_high = np.random.uniform(2.5, 5.0, n_high)
        spo2_high = np.random.uniform(86.0, 92.5, n_high)
        spo2_drop_high = (95.0 - spo2_high).clip(min=0)
        temp_high = np.random.normal(38.6, 0.5, n_high).clip(38.1, 40.2)
        temp_diff_high = temp_high - 36.6
        elev_sed_high = np.random.choice([0, 1], size=n_high, p=[0.1, 0.9])

        X_high = np.column_stack([
            hr_high, hr_std_high, hrv_high, hr_z_high, steps_high, sleep_high,
            spo2_high, spo2_drop_high, temp_high, temp_diff_high, elev_sed_high
        ])
        y_high = np.full(n_high, 2, dtype=int) # 2 = High

        X = np.vstack([X_low, X_mod, X_high])
        y = np.concatenate([y_low, y_mod, y_high])
        return X, y

    def _bootstrap_initial_training(self):
        X, y = self._generate_synthetic_training_corpus()
        self.model.fit(X, y)
        self.is_trained = True

    def assess_risk(
        self, 
        df_features: pd.DataFrame, 
        baseline: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluates overall risk on latest window of sensor readings.
        """
        if df_features.empty:
            return {
                "overall_risk_level": "Low",
                "risk_score_numeric": 12.0,
                "anomaly_probability": 0.05,
                "primary_concerns": ["All monitored vitals are within normal range."],
                "risk_factors": [],
                "wellness_recommendation": "Your vitals are steady. Maintain your routine of hydration and regular sleep."
            }

        latest = df_features.iloc[-1]
        X_sample = prepare_feature_matrix(df_features.tail(1))

        probs = self.model.predict_proba(X_sample)[0]  # [prob_low, prob_mod, prob_high]
        risk_class_idx = int(np.argmax(probs))
        risk_level = self.classes_[risk_class_idx]
        
        # Weighted continuous risk score 0 - 100
        risk_score_numeric = float(probs[0] * 10.0 + probs[1] * 50.0 + probs[2] * 90.0)
        anomaly_prob = float(probs[1] * 0.5 + probs[2] * 1.0)

        # Feature contributions
        importances = self.model.feature_importances_
        feature_weights = []
        for col_name, imp in zip(FEATURE_COLUMNS, importances):
            val = latest.get(col_name, 0.0)
            feature_weights.append({
                "feature": col_name,
                "importance": float(imp),
                "value": float(val)
            })

        # Generate human-readable risk factors & explanations
        factors: List[Dict[str, Any]] = []
        concerns: List[str] = []

        hr = float(latest.get("heart_rate", 70.0))
        spo2 = float(latest.get("spo2", 98.0))
        temp = float(latest.get("temperature", 36.6))
        sleep = float(latest.get("sleep_hours", 7.5))
        z_hr = float(latest.get("hr_zscore", 0.0))
        is_elev_sed = int(latest.get("is_elevated_sedentary", 0))

        if hr >= 95 or z_hr >= 2.0:
            impact = "High" if hr >= 105 else "Moderate"
            factors.append({
                "feature": "Heart Rate Dynamics",
                "impact": impact,
                "contribution": 0.35 if impact == "High" else 0.2,
                "description": f"Heart rate of {hr:.0f} BPM is elevated ({z_hr:+.1f}σ from baseline)."
            })
            concerns.append(f"Elevated heart rate (+{z_hr:.1f}σ deviation from personal baseline).")

        if spo2 < 95.0:
            impact = "High" if spo2 < 91.0 else "Moderate"
            factors.append({
                "feature": "Blood Oxygen (SpO2)",
                "impact": impact,
                "contribution": 0.40 if impact == "High" else 0.25,
                "description": f"SpO2 saturation is {spo2:.1f}% (below standard threshold)."
            })
            concerns.append(f"Sub-optimal blood oxygen saturation ({spo2:.1f}%).")

        if temp >= 37.5:
            impact = "High" if temp >= 38.3 else "Moderate"
            factors.append({
                "feature": "Body Temperature",
                "impact": impact,
                "contribution": 0.30 if impact == "High" else 0.15,
                "description": f"Temperature elevated to {temp:.1f}°C."
            })
            concerns.append(f"Elevated body temperature ({temp:.1f}°C).")

        if sleep < 6.0:
            factors.append({
                "feature": "Sleep Duration",
                "impact": "Moderate" if sleep < 4.5 else "Low",
                "contribution": 0.15,
                "description": f"Recorded sleep duration is {sleep:.1f} hours."
            })
            if sleep < 5.0:
                concerns.append(f"Significant sleep debt ({sleep:.1f}h recorded).")

        if is_elev_sed == 1 and temp < 37.5:
            factors.append({
                "feature": "Activity / HR Decoupling",
                "impact": "Moderate",
                "contribution": 0.20,
                "description": "High heart rate observed during sedentary inactivity."
            })
            concerns.append("Resting tachycardia without active exertion.")

        if not concerns:
            concerns.append("All primary vitals within normal baseline range.")
            factors.append({
                "feature": "Vitals Equilibrium",
                "impact": "Low",
                "contribution": 0.05,
                "description": "Heart rate, oxygen, temperature, and sleep are well balanced."
            })

        # Formulate wellness guidance
        if risk_level == "High":
            recommendation = "Multiple vital indicators are significantly outside baseline parameters. Rest in a calm environment, re-measure vitals in 15 minutes, and seek medical consultation if symptoms (shortness of breath, chest discomfort, or high fever) persist."
        elif risk_level == "Moderate":
            recommendation = "Mild deviations detected from your normal baseline. Ensure adequate hydration, rest, avoid stimulants (caffeine/energy drinks), and monitor trends over the next few hours."
        else:
            recommendation = "Your health metrics are stable and well within your personal baseline bounds. Keep up your healthy lifestyle, regular sleep, and daily physical activity."

        return {
            "overall_risk_level": risk_level,
            "risk_score_numeric": round(risk_score_numeric, 1),
            "anomaly_probability": round(anomaly_prob, 2),
            "primary_concerns": concerns,
            "risk_factors": factors,
            "wellness_recommendation": recommendation
        }
