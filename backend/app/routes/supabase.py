from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import SensorReading, AnomalyAlert
from backend.services.supabase_service import supabase_service

router = APIRouter(prefix="/api/supabase", tags=["Supabase Cloud Sync"])

class SupabaseConfigRequest(BaseModel):
    url: str
    key: str
    save_to_env: bool = True

class TestConnectionRequest(BaseModel):
    url: Optional[str] = None
    key: Optional[str] = None

@router.get("/status")
def get_supabase_status() -> Dict[str, Any]:
    """
    Returns current Supabase connection status, project details, and sync statistics.
    """
    return supabase_service.get_status()

@router.post("/test")
def test_supabase_connection(req: TestConnectionRequest = TestConnectionRequest()) -> Dict[str, Any]:
    """
    Tests live connectivity to Supabase using either specified or stored credentials.
    """
    return supabase_service.test_connection(url=req.url, key=req.key)

@router.post("/config")
def update_supabase_config(req: SupabaseConfigRequest) -> Dict[str, Any]:
    """
    Updates the Supabase URL and API Key, tests connection, and persists to .env.
    """
    if not req.url or not req.key:
        raise HTTPException(status_code=400, detail="Both 'url' and 'key' are required.")

    supabase_service.update_credentials(url=req.url, key=req.key, save_to_env=req.save_to_env)
    test_res = supabase_service.test_connection()
    return {
        "message": "Supabase configuration updated.",
        "test_result": test_res,
        "status": supabase_service.get_status()
    }

@router.post("/sync")
def sync_to_supabase(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Pushes recent local sensor readings and active anomaly alerts up to Supabase.
    """
    if not supabase_service.url or not supabase_service.key:
        return {
            "success": False,
            "message": "Supabase credentials are not configured yet. Please configure URL and Key in the Supabase Hub.",
            "synced_readings": 0,
            "synced_alerts": 0
        }

    # Fetch last 200 readings
    readings = db.query(SensorReading).order_by(SensorReading.timestamp.desc()).limit(200).all()
    reading_dicts = [
        {
            "timestamp": r.timestamp,
            "heart_rate": r.heart_rate,
            "steps": r.steps,
            "activity": r.activity,
            "sleep_hours": r.sleep_hours,
            "spo2": r.spo2,
            "temperature": r.temperature,
            "is_resting": r.is_resting
        }
        for r in readings
    ]

    readings_result = supabase_service.sync_readings_to_supabase(reading_dicts)

    # Fetch anomaly alerts
    alerts = db.query(AnomalyAlert).order_by(AnomalyAlert.timestamp.desc()).limit(50).all()
    alert_dicts = [
        {
            "timestamp": a.timestamp,
            "parameter": a.parameter,
            "metric_value": a.metric_value,
            "baseline_value": a.baseline_value,
            "deviation_zscore": a.deviation_zscore,
            "severity": a.severity,
            "detector_type": a.detector_type,
            "explanation": a.explanation,
            "recommendation": a.recommendation,
            "is_acknowledged": a.is_acknowledged
        }
        for a in alerts
    ]
    alerts_result = supabase_service.sync_anomalies_to_supabase(alert_dicts)

    return {
        "success": readings_result.get("success", False),
        "message": readings_result.get("message", "Sync executed."),
        "synced_readings": readings_result.get("synced", 0),
        "synced_alerts": alerts_result.get("synced", 0),
        "timestamp": supabase_service.last_sync_time
    }

@router.get("/schema")
def get_supabase_schema() -> Dict[str, str]:
    """
    Returns SQL statements for setting up Supabase database tables.
    """
    return {"sql": supabase_service.get_sql_migration()}
