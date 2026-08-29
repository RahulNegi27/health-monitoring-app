import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.models import SensorReading, DailyAggregate, AnomalyAlert, UserProfile
from backend.app.schemas import (
    SensorReadingCreate, HealthSummaryOut, MetricCard, 
    RiskScoreOut, AnomalyAlertOut, UserProfileOut
)
from backend.analytics.etl import (
    clean_sensor_dataframe, aggregate_daily_metrics, compute_user_baseline
)
from backend.analytics.feature_engineering import extract_time_series_features
from backend.models.anomaly_detector import AnomalyDetector
from backend.models.risk_classifier import HealthRiskClassifier

class HealthService:
    def __init__(self):
        self.anomaly_detector = AnomalyDetector()
        self.risk_classifier = HealthRiskClassifier()

    def get_or_create_user_profile(self, db: Session) -> UserProfile:
        profile = db.query(UserProfile).filter(UserProfile.id == 1).first()
        if not profile:
            profile = UserProfile(
                id=1,
                username="Rahul",
                age=24,
                resting_hr_mean=70.0,
                resting_hr_std=6.0,
                target_steps=8000,
                target_sleep=7.5,
                normal_spo2_min=95.0,
                normal_temp_mean=36.6
            )
            db.add(profile)
            db.commit()
            db.refresh(profile)
        return profile

    def ingest_sensor_readings(
        self, 
        db: Session, 
        readings: List[Dict[str, Any]]
    ) -> int:
        """
        Stores sensor readings, re-calculates aggregates, runs anomaly detection, and logs alerts.
        """
        if not readings:
            return 0

        db_records = []
        for r in readings:
            ts = r.get("timestamp") or datetime.utcnow()
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            
            rec = SensorReading(
                timestamp=ts,
                heart_rate=float(r["heart_rate"]),
                steps=int(r.get("steps", 0)),
                activity=str(r.get("activity", "Sedentary")),
                sleep_hours=float(r.get("sleep_hours", 0.0)),
                spo2=float(r.get("spo2", 98.0)),
                temperature=float(r.get("temperature", 36.6)),
                is_resting=bool(r.get("is_resting", False))
            )
            db_records.append(rec)

        db.bulk_save_objects(db_records)
        db.commit()

        # Re-compute daily aggregates and check anomalies on recent batch
        self.sync_daily_aggregates_and_anomalies(db)
        return len(db_records)

    def sync_daily_aggregates_and_anomalies(self, db: Session):
        """
        Recomputes daily tables, extracts features, and evaluates rule & ML anomaly detectors.
        """
        # Fetch last 14 days of readings
        cutoff = datetime.utcnow() - timedelta(days=14)
        recent_readings = db.query(SensorReading).filter(SensorReading.timestamp >= cutoff).order_by(SensorReading.timestamp.asc()).all()
        if not recent_readings:
            return

        # Convert to DataFrame
        data = [{
            "timestamp": r.timestamp,
            "heart_rate": r.heart_rate,
            "steps": r.steps,
            "activity": r.activity,
            "sleep_hours": r.sleep_hours,
            "spo2": r.spo2,
            "temperature": r.temperature,
            "is_resting": r.is_resting
        } for r in recent_readings]

        df = pd.DataFrame(data)
        cleaned_df = clean_sensor_dataframe(df)

        # 1. Update Daily Aggregates
        daily_df = aggregate_daily_metrics(cleaned_df)
        for _, row in daily_df.iterrows():
            d_val = row["date"]
            daily_rec = db.query(DailyAggregate).filter(DailyAggregate.date == d_val).first()
            if not daily_rec:
                daily_rec = DailyAggregate(date=d_val)
                db.add(daily_rec)
            
            daily_rec.resting_hr = row.get("resting_hr")
            daily_rec.avg_hr = row.get("avg_hr")
            daily_rec.min_hr = row.get("min_hr")
            daily_rec.max_hr = row.get("max_hr")
            daily_rec.total_steps = int(row.get("total_steps", 0))
            daily_rec.total_sleep = float(row.get("total_sleep", 0.0))
            daily_rec.avg_spo2 = row.get("avg_spo2")
            daily_rec.min_spo2 = row.get("min_spo2")
            daily_rec.avg_temp = row.get("avg_temp", 36.6)

        db.commit()

        # 2. Derive Dynamic Personal Baseline
        user_profile = self.get_or_create_user_profile(db)
        derived_base = compute_user_baseline(daily_df, window_days=7)
        
        # Merge profile overrides with derived baseline
        baseline = {
            "resting_hr_mean": user_profile.resting_hr_mean or derived_base["resting_hr_mean"],
            "resting_hr_std": user_profile.resting_hr_std or derived_base["resting_hr_std"],
            "avg_daily_steps": user_profile.target_steps or derived_base["avg_daily_steps"],
            "avg_sleep_hours": user_profile.target_sleep or derived_base["avg_sleep_hours"],
            "normal_spo2_min": user_profile.normal_spo2_min or derived_base["normal_spo2_min"],
            "normal_temp_mean": user_profile.normal_temp_mean or derived_base["normal_temp_mean"],
        }

        # 3. Extract Features for Anomaly Detection
        df_features = extract_time_series_features(cleaned_df, baseline)

        # 4. Run Hybrid Anomaly Detectors
        rule_alerts = self.anomaly_detector.detect_rule_based_anomalies(cleaned_df.tail(48), baseline)
        ml_alerts = self.anomaly_detector.detect_ml_anomalies(df_features.tail(48), baseline)
        all_detected = rule_alerts + ml_alerts

        # 5. Deduplicate and persist new alerts (avoid duplicate alerts in same hour)
        for alert_dict in all_detected:
            alert_ts = alert_dict["timestamp"]
            param = alert_dict["parameter"]
            # Check if similar alert exists within ±1 hour
            existing = db.query(AnomalyAlert).filter(
                AnomalyAlert.parameter == param,
                AnomalyAlert.timestamp >= (alert_ts - timedelta(hours=1)),
                AnomalyAlert.timestamp <= (alert_ts + timedelta(hours=1))
            ).first()

            if not existing:
                new_alert = AnomalyAlert(
                    timestamp=alert_ts,
                    parameter=param,
                    metric_value=alert_dict["metric_value"],
                    baseline_value=alert_dict.get("baseline_value"),
                    deviation_zscore=alert_dict.get("deviation_zscore"),
                    severity=alert_dict.get("severity", "moderate"),
                    detector_type=alert_dict.get("detector_type", "rule"),
                    explanation=alert_dict["explanation"],
                    recommendation=alert_dict["recommendation"]
                )
                db.add(new_alert)

        db.commit()

    def get_health_summary(self, db: Session) -> HealthSummaryOut:
        """
        Builds today's health dashboard summary card metrics and alerts.
        """
        latest_reading = db.query(SensorReading).order_by(desc(SensorReading.timestamp)).first()
        today_date = date.today()
        today_agg = db.query(DailyAggregate).filter(DailyAggregate.date == today_date).first()
        
        # If no today_agg, get latest available aggregate
        if not today_agg:
            today_agg = db.query(DailyAggregate).order_by(desc(DailyAggregate.date)).first()

        profile = self.get_or_create_user_profile(db)

        # Defaults if database is empty
        cur_hr = latest_reading.heart_rate if latest_reading else 72.0
        cur_steps = today_agg.total_steps if today_agg else (latest_reading.steps if latest_reading else 0)
        cur_sleep = today_agg.total_sleep if today_agg else (latest_reading.sleep_hours if latest_reading else 7.2)
        cur_spo2 = latest_reading.spo2 if latest_reading else 98.0
        cur_temp = latest_reading.temperature if latest_reading else 36.6
        rest_hr = today_agg.resting_hr if today_agg and today_agg.resting_hr else 68.0

        # Evaluate card statuses
        hr_status = "normal"
        if cur_hr > 105 or cur_hr < 50:
            hr_status = "critical"
        elif cur_hr > 90:
            hr_status = "warning"

        spo2_status = "normal"
        if cur_spo2 < 90.0:
            spo2_status = "critical"
        elif cur_spo2 < profile.normal_spo2_min:
            spo2_status = "warning"

        temp_status = "normal"
        if cur_temp >= 38.3:
            temp_status = "critical"
        elif cur_temp >= 37.5:
            temp_status = "warning"

        sleep_status = "normal" if cur_sleep >= 6.5 else ("warning" if cur_sleep >= 5.0 else "critical")
        steps_status = "normal" if cur_steps >= 6000 else "warning"

        # Fetch recent 5 unacknowledged alerts
        recent_alerts_db = db.query(AnomalyAlert).order_by(desc(AnomalyAlert.timestamp)).limit(5).all()
        recent_alerts = [AnomalyAlertOut.model_validate(a) for a in recent_alerts_db]

        wellness_status = "Optimal"
        if any(a.severity == "severe" for a in recent_alerts[:2]):
            wellness_status = "Attention Required"
        elif any(a.severity == "moderate" for a in recent_alerts[:2]):
            wellness_status = "Moderate Strain"

        return HealthSummaryOut(
            timestamp=latest_reading.timestamp if latest_reading else datetime.utcnow(),
            heart_rate=MetricCard(
                current=round(cur_hr, 1),
                unit="BPM",
                baseline=profile.resting_hr_mean,
                status=hr_status,
                trend_direction="up" if cur_hr > profile.resting_hr_mean + 5 else ("down" if cur_hr < profile.resting_hr_mean - 5 else "stable"),
                subtext=f"Normal baseline ~{profile.resting_hr_mean:.0f} BPM"
            ),
            resting_hr=MetricCard(
                current=round(rest_hr, 1),
                unit="BPM",
                baseline=profile.resting_hr_mean,
                status="warning" if rest_hr > (profile.resting_hr_mean + 12) else "normal",
                trend_direction="stable",
                subtext="Calculated during inactive periods"
            ),
            steps=MetricCard(
                current=float(cur_steps),
                unit="steps",
                baseline=float(profile.target_steps),
                status=steps_status,
                trend_direction="up",
                subtext=f"Target: {profile.target_steps:,} steps"
            ),
            sleep=MetricCard(
                current=round(cur_sleep, 1),
                unit="hours",
                baseline=profile.target_sleep,
                status=sleep_status,
                trend_direction="stable",
                subtext=f"Target: {profile.target_sleep} hrs"
            ),
            spo2=MetricCard(
                current=round(cur_spo2, 1),
                unit="%",
                baseline=profile.normal_spo2_min,
                status=spo2_status,
                trend_direction="stable",
                subtext="Standard safe: ≥95%"
            ),
            temperature=MetricCard(
                current=round(cur_temp, 1),
                unit="°C",
                baseline=profile.normal_temp_mean,
                status=temp_status,
                trend_direction="stable",
                subtext="Normal ~36.6°C"
            ),
            overall_wellness_status=wellness_status,
            active_alerts_count=len(recent_alerts_db),
            recent_alerts=recent_alerts
        )

    def get_risk_assessment(self, db: Session) -> RiskScoreOut:
        """
        Runs ML Random Forest risk classifier on the latest health features.
        """
        cutoff = datetime.utcnow() - timedelta(days=7)
        recent_readings = db.query(SensorReading).filter(SensorReading.timestamp >= cutoff).order_by(SensorReading.timestamp.asc()).all()
        
        profile = self.get_or_create_user_profile(db)
        baseline = {
            "resting_hr_mean": profile.resting_hr_mean,
            "resting_hr_std": profile.resting_hr_std,
            "avg_daily_steps": profile.target_steps,
            "avg_sleep_hours": profile.target_sleep,
            "normal_spo2_min": profile.normal_spo2_min,
            "normal_temp_mean": profile.normal_temp_mean
        }

        if not recent_readings:
            return RiskScoreOut(
                overall_risk_level="Low",
                risk_score_numeric=10.0,
                anomaly_probability=0.04,
                primary_concerns=["No abnormal deviations detected."],
                risk_factors=[],
                wellness_recommendation="Vitals are well balanced. Maintain consistent sleep and activity."
            )

        data = [{
            "timestamp": r.timestamp,
            "heart_rate": r.heart_rate,
            "steps": r.steps,
            "activity": r.activity,
            "sleep_hours": r.sleep_hours,
            "spo2": r.spo2,
            "temperature": r.temperature,
            "is_resting": r.is_resting
        } for r in recent_readings]

        df = clean_sensor_dataframe(pd.DataFrame(data))
        df_features = extract_time_series_features(df, baseline)
        
        risk_res = self.risk_classifier.assess_risk(df_features, baseline)
        return RiskScoreOut(**risk_res)

    def get_health_trends(self, db: Session, days: int = 7) -> Dict[str, Any]:
        """
        Returns structured time-series data for front-end charts:
        - Daily Aggregates (Date, Resting HR, Steps, Sleep, SpO2, Temp)
        - High-frequency recent 48-hour readings (Timestamp, HR, Steps, SpO2, Activity)
        - Personal baseline reference lines
        """
        profile = self.get_or_create_user_profile(db)

        # 1. Daily Aggregates
        daily_records = db.query(DailyAggregate).order_by(DailyAggregate.date.desc()).limit(days).all()
        daily_records.reverse()

        daily_data = [{
            "date": str(d.date),
            "resting_hr": d.resting_hr,
            "avg_hr": d.avg_hr,
            "min_hr": d.min_hr,
            "max_hr": d.max_hr,
            "total_steps": d.total_steps,
            "total_sleep": d.total_sleep,
            "avg_spo2": d.avg_spo2,
            "min_spo2": d.min_spo2,
            "avg_temp": d.avg_temp
        } for d in daily_records]

        # 2. Hourly/Sub-hourly High-Resolution Readings (last 48 hours)
        cutoff_recent = datetime.utcnow() - timedelta(hours=48)
        recent_samples = db.query(SensorReading).filter(SensorReading.timestamp >= cutoff_recent).order_by(SensorReading.timestamp.asc()).all()

        timeline_data = [{
            "timestamp": s.timestamp.isoformat(),
            "heart_rate": s.heart_rate,
            "steps": s.steps,
            "spo2": s.spo2,
            "temperature": s.temperature,
            "activity": s.activity,
            "is_resting": s.is_resting
        } for s in recent_samples]

        return {
            "baseline": {
                "resting_hr_mean": profile.resting_hr_mean,
                "resting_hr_upper": profile.resting_hr_mean + 2.0 * profile.resting_hr_std,
                "resting_hr_lower": profile.resting_hr_mean - 2.0 * profile.resting_hr_std,
                "target_steps": profile.target_steps,
                "target_sleep": profile.target_sleep,
                "min_spo2": profile.normal_spo2_min
            },
            "daily_trends": daily_data,
            "timeline": timeline_data
        }

health_service = HealthService()
