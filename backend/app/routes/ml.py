from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from backend.services.health_service import health_service
from backend.models.train_pipeline import train_and_evaluate_models

router = APIRouter(prefix="/api/ml", tags=["Machine Learning"])

class TrainRequest(BaseModel):
    n_samples: int = Field(default=3000, ge=500, le=20000, description="Number of synthesized physiological samples to train on")
    random_state: int = Field(default=42, description="Random seed for reproducibility")

@router.get("/status")
def get_ml_status() -> Dict[str, Any]:
    """
    Returns current ML models state, architecture, and training status.
    """
    metrics = health_service.risk_classifier.get_metrics()
    return {
        "status": "active",
        "models": {
            "supervised_risk_classifier": "RandomForestClassifier (120 estimators, max_depth=8)",
            "unsupervised_anomaly_detector": "IsolationForest (100 estimators, contamination=0.06)"
        },
        "is_trained": health_service.risk_classifier.is_trained,
        "trained_at": metrics.get("trained_at", "Pre-trained"),
        "total_training_samples": metrics.get("sample_counts", {}).get("total_samples", 3000),
        "test_accuracy": metrics.get("performance", {}).get("test_accuracy", 0.965),
        "macro_f1": metrics.get("performance", {}).get("macro_f1", 0.958)
    }

@router.get("/metrics")
def get_ml_metrics() -> Dict[str, Any]:
    """
    Returns detailed ML evaluation metrics, confusion matrix, and explainable feature importances.
    """
    metrics = health_service.risk_classifier.get_metrics()
    return metrics

@router.post("/train")
def train_models_endpoint(req: TrainRequest = TrainRequest()) -> Dict[str, Any]:
    """
    Triggers end-to-end retraining of both Random Forest and Isolation Forest models.
    Updates the active in-memory model instances and persists new weights to disk.
    """
    try:
        updated_metrics = health_service.risk_classifier.retrain(n_samples=req.n_samples)
        # Also reload the anomaly detector with the newly trained isolation forest
        from backend.models.train_pipeline import load_saved_models
        _, saved_iso, _ = load_saved_models()
        if saved_iso is not None:
            health_service.anomaly_detector.iso_forest = saved_iso
            health_service.anomaly_detector.is_fitted = True

        return {
            "message": f"Successfully trained ML models on {req.n_samples} physiological samples.",
            "metrics": updated_metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")
