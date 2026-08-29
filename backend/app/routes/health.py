from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from backend.app.database import get_db
from backend.app.models import AnomalyAlert, SensorReading
from backend.app.schemas import (
    HealthSummaryOut, RiskScoreOut, AnomalyAlertOut, 
    SensorReadingCreate, SensorReadingOut
)
from backend.services.health_service import health_service

router = APIRouter(prefix="/api/health", tags=["Health & Vitals"])

@router.get("/summary", response_model=HealthSummaryOut)
def get_health_summary(db: Session = Depends(get_db)):
    """
    Returns today's health status, real-time vitals, baseline comparison, and active alerts.
    """
    return health_service.get_health_summary(db)

@router.get("/risk-score", response_model=RiskScoreOut)
def get_risk_score(db: Session = Depends(get_db)):
    """
    Returns ML Random Forest Risk Assessment (Low / Moderate / High) with explainable risk factors.
    """
    return health_service.get_risk_assessment(db)

@router.get("/trends")
def get_health_trends(
    days: int = Query(7, ge=1, le=60), 
    db: Session = Depends(get_db)
):
    """
    Returns time-series trend data for interactive charts (HR, steps, sleep, SpO2, temp).
    """
    return health_service.get_health_trends(db, days=days)

@router.get("/anomalies", response_model=List[AnomalyAlertOut])
def get_anomalies(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Returns historical list of detected anomalies with severity, detector type, and guidance.
    """
    alerts = db.query(AnomalyAlert).order_by(AnomalyAlert.timestamp.desc()).limit(limit).all()
    return alerts

@router.post("/anomalies/{alert_id}/acknowledge")
def acknowledge_anomaly(alert_id: int, db: Session = Depends(get_db)):
    """
    Marks an anomaly alert as reviewed by the user.
    """
    alert = db.query(AnomalyAlert).filter(AnomalyAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_acknowledged = True
    db.commit()
    return {"status": "success", "message": f"Alert {alert_id} acknowledged"}

@router.post("/ingest")
def ingest_reading(reading: SensorReadingCreate, db: Session = Depends(get_db)):
    """
    Ingests a single raw sensor reading from smartwatch/phone.
    """
    count = health_service.ingest_sensor_readings(db, [reading.model_dump()])
    return {"status": "success", "ingested_count": count}

@router.post("/ingest/batch")
def ingest_batch_readings(readings: List[SensorReadingCreate], db: Session = Depends(get_db)):
    """
    Ingests a batch of sensor readings.
    """
    raw_list = [r.model_dump() for r in readings]
    count = health_service.ingest_sensor_readings(db, raw_list)
    return {"status": "success", "ingested_count": count}
