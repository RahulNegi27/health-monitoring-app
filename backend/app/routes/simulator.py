from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import asyncio

from backend.app.database import get_db, SessionLocal
from backend.app.models import SensorReading, DailyAggregate, AnomalyAlert
from backend.app.schemas import ScenarioRequest, SimulatorStatusOut
from backend.services.simulator import simulator_instance
from backend.services.health_service import health_service

router = APIRouter(prefix="/api/simulator", tags=["Sensor Simulator"])

_stream_running = False
_stream_task = None

async def _streaming_worker(scenario: str):
    global _stream_running
    while _stream_running:
        sample = simulator_instance.generate_single_live_sample(scenario=scenario)
        db = SessionLocal()
        try:
            health_service.ingest_sensor_readings(db, [sample])
        except Exception as e:
            print(f"Error in stream ingestion: {e}")
        finally:
            db.close()
        await asyncio.sleep(3.0)  # Emit every 3 seconds

@router.post("/generate")
def generate_scenario(req: ScenarioRequest, db: Session = Depends(get_db)):
    """
    Generates realistic multi-day health time series for preset scenario:
    - 'normal': Healthy circadian baseline
    - 'fever': Infection with fever, elevated resting HR, degraded sleep
    - 'stress': Chronic stress, elevated HR during sedentary hours, sleep debt
    - 'hypoxia': Sleep apnea / SpO2 nocturnal drops below 90%
    - 'tachycardia': Sudden resting heart rate spikes
    """
    # 1. Clear existing readings to ensure clean scenario demonstration
    db.query(SensorReading).delete()
    db.query(DailyAggregate).delete()
    db.query(AnomalyAlert).delete()
    db.commit()

    # 2. Generate scenario data
    samples = simulator_instance.generate_scenario_data(scenario=req.scenario, days=req.days)
    count = health_service.ingest_sensor_readings(db, samples)

    return {
        "status": "success",
        "scenario": req.scenario,
        "days": req.days,
        "samples_generated": count,
        "message": f"Successfully generated {count} readings for '{req.scenario}' scenario."
    }

@router.post("/stream/toggle")
async def toggle_stream(
    scenario: str = "normal", 
    db: Session = Depends(get_db)
):
    """
    Toggles live real-time sensor telemetry streaming (emits sample every 3 seconds).
    """
    global _stream_running, _stream_task
    if _stream_running:
        _stream_running = False
        if _stream_task and not _stream_task.done():
            _stream_task.cancel()
        return {"status": "stopped", "is_streaming": False, "message": "Live sensor streaming stopped."}
    else:
        _stream_running = True
        simulator_instance.current_scenario = scenario
        _stream_task = asyncio.create_task(_streaming_worker(scenario))
        return {
            "status": "started", 
            "is_streaming": True, 
            "scenario": scenario,
            "message": f"Live sensor streaming started for scenario '{scenario}'."
        }

@router.get("/status", response_model=SimulatorStatusOut)
def get_simulator_status(db: Session = Depends(get_db)):
    """
    Returns current simulator streaming state and database record count.
    """
    global _stream_running
    readings_count = db.query(SensorReading).count()
    last_reading = db.query(SensorReading).order_by(SensorReading.timestamp.desc()).first()
    
    return SimulatorStatusOut(
        is_streaming=_stream_running,
        current_scenario=simulator_instance.current_scenario,
        readings_count=readings_count,
        last_reading_time=last_reading.timestamp if last_reading else None
    )

@router.post("/reset")
def reset_database(db: Session = Depends(get_db)):
    """
    Clears all sensor data and resets to initial default scenario.
    """
    db.query(SensorReading).delete()
    db.query(DailyAggregate).delete()
    db.query(AnomalyAlert).delete()
    db.commit()

    samples = simulator_instance.generate_scenario_data(scenario="normal", days=7)
    count = health_service.ingest_sensor_readings(db, samples)
    return {"status": "success", "message": f"Database reset to clean 7-day normal baseline ({count} readings)."}
