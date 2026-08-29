from datetime import datetime, date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class SensorReadingBase(BaseModel):
    heart_rate: float = Field(..., ge=30, le=250, description="Heart rate in BPM")
    steps: int = Field(0, ge=0, description="Step count in window")
    activity: str = Field("Sedentary", description="Activity level: Sedentary, Walking, Running, Sleeping")
    sleep_hours: float = Field(0.0, ge=0, le=24, description="Sleep duration in hours")
    spo2: float = Field(98.0, ge=60, le=100, description="Blood oxygen saturation percentage")
    temperature: float = Field(36.6, ge=30.0, le=45.0, description="Body temperature in Celsius")
    is_resting: bool = Field(False, description="Whether reading occurred during resting/sedentary state")

class SensorReadingCreate(SensorReadingBase):
    timestamp: Optional[datetime] = None

class SensorReadingOut(SensorReadingBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: datetime

class DailyAggregateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: date
    resting_hr: Optional[float] = None
    avg_hr: Optional[float] = None
    min_hr: Optional[float] = None
    max_hr: Optional[float] = None
    total_steps: int
    total_sleep: float
    avg_spo2: Optional[float] = None
    min_spo2: Optional[float] = None
    avg_temp: float
    anomaly_count: int

class AnomalyAlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: datetime
    parameter: str
    metric_value: float
    baseline_value: Optional[float] = None
    deviation_zscore: Optional[float] = None
    severity: str
    detector_type: str
    explanation: str
    recommendation: str
    is_acknowledged: bool

class UserProfileBase(BaseModel):
    username: str = "Rahul"
    age: int = 24
    resting_hr_mean: float = 70.0
    resting_hr_std: float = 6.0
    target_steps: int = 8000
    target_sleep: float = 7.5
    normal_spo2_min: float = 95.0
    normal_temp_mean: float = 36.6

class UserProfileOut(UserProfileBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    updated_at: datetime

class UserProfileUpdate(BaseModel):
    resting_hr_mean: Optional[float] = None
    resting_hr_std: Optional[float] = None
    target_steps: Optional[int] = None
    target_sleep: Optional[float] = None
    normal_spo2_min: Optional[float] = None
    normal_temp_mean: Optional[float] = None

class RiskFactor(BaseModel):
    feature: str
    impact: str           # "High", "Moderate", "Low"
    contribution: float   # 0.0 to 1.0
    description: str

class RiskScoreOut(BaseModel):
    overall_risk_level: str   # "Low", "Moderate", "High"
    risk_score_numeric: float # 0 - 100
    anomaly_probability: float
    primary_concerns: List[str]
    risk_factors: List[RiskFactor]
    wellness_recommendation: str
    disclaimer: str = "This analysis is for wellness and pattern tracking only. It is not a medical diagnosis."

class MetricCard(BaseModel):
    current: float
    unit: str
    baseline: Optional[float] = None
    status: str            # "normal", "warning", "critical"
    trend_direction: str   # "stable", "up", "down"
    subtext: str

class HealthSummaryOut(BaseModel):
    timestamp: datetime
    heart_rate: MetricCard
    resting_hr: MetricCard
    steps: MetricCard
    sleep: MetricCard
    spo2: MetricCard
    temperature: MetricCard
    overall_wellness_status: str
    active_alerts_count: int
    recent_alerts: List[AnomalyAlertOut]

class ScenarioRequest(BaseModel):
    scenario: str = Field(..., description="normal, fever, stress, hypoxia, tachycardia")
    days: int = Field(7, ge=1, le=30)

class SimulatorStatusOut(BaseModel):
    is_streaming: bool
    current_scenario: Optional[str]
    readings_count: int
    last_reading_time: Optional[datetime]
