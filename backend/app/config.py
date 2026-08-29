import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Health Monitor & Anomaly Detection System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "sqlite:///./health_monitoring.db"
    
    # Clinical / Physiological Reference Norms (Sensible Defaults)
    DEFAULT_RESTING_HR_MEAN: float = 70.0      # bpm
    DEFAULT_RESTING_HR_STD: float = 6.0        # bpm
    DEFAULT_SPO2_BASELINE: float = 98.0        # %
    DEFAULT_MIN_SAFE_SPO2: float = 94.0        # %
    DEFAULT_DAILY_STEP_TARGET: int = 8000      # steps
    DEFAULT_DAILY_SLEEP_TARGET: float = 7.5    # hours
    DEFAULT_BODY_TEMP_MEAN: float = 36.6       # °C
    
    # Anomaly Sensitivity (Z-score threshold)
    ZSCORE_THRESHOLD_WARNING: float = 2.0
    ZSCORE_THRESHOLD_CRITICAL: float = 3.0
    
    # ML Model Configs
    ISOLATION_FOREST_CONTAMINATION: float = 0.05
    RANDOM_STATE: int = 42

settings = Settings()
