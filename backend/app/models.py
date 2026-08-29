from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, Date, Text
from backend.app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=utc_now, index=True)
    heart_rate = Column(Float, nullable=False)           # bpm
    steps = Column(Integer, default=0)                   # count in this sample window
    activity = Column(String(50), default="Sedentary")   # Sedentary, Walking, Running, Sleeping
    sleep_hours = Column(Float, default=0.0)             # Cumulative or window sleep
    spo2 = Column(Float, nullable=False)                 # %
    temperature = Column(Float, default=36.6)            # °C
    is_resting = Column(Boolean, default=False)          # Flagged resting period

class DailyAggregate(Base):
    __tablename__ = "daily_aggregates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    date = Column(Date, unique=True, index=True, nullable=False)
    resting_hr = Column(Float, nullable=True)
    avg_hr = Column(Float, nullable=True)
    min_hr = Column(Float, nullable=True)
    max_hr = Column(Float, nullable=True)
    total_steps = Column(Integer, default=0)
    total_sleep = Column(Float, default=0.0)
    avg_spo2 = Column(Float, nullable=True)
    min_spo2 = Column(Float, nullable=True)
    avg_temp = Column(Float, default=36.6)
    anomaly_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utc_now)

class AnomalyAlert(Base):
    __tablename__ = "anomaly_alerts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=utc_now, index=True)
    parameter = Column(String(50), nullable=False)       # Heart Rate, SpO2, Sleep, Temperature, Activity
    metric_value = Column(Float, nullable=False)
    baseline_value = Column(Float, nullable=True)
    deviation_zscore = Column(Float, nullable=True)
    severity = Column(String(20), default="moderate")    # mild, moderate, severe
    detector_type = Column(String(50), default="rule")   # rule_based, isolation_forest, hybrid
    explanation = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=False)
    is_acknowledged = Column(Boolean, default=False)

class UserProfile(Base):
    __tablename__ = "user_profile"

    id = Column(Integer, primary_key=True, default=1)
    username = Column(String(100), default="Rahul")
    age = Column(Integer, default=24)
    resting_hr_mean = Column(Float, default=70.0)
    resting_hr_std = Column(Float, default=6.0)
    target_steps = Column(Integer, default=8000)
    target_sleep = Column(Float, default=7.5)
    normal_spo2_min = Column(Float, default=95.0)
    normal_temp_mean = Column(Float, default=36.6)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
