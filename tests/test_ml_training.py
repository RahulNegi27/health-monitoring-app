import pytest
import os
import numpy as np
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.models.train_pipeline import (
    generate_robust_training_data,
    train_and_evaluate_models,
    load_saved_models,
    MODEL_DIR,
    RF_MODEL_PATH,
    ISO_MODEL_PATH,
    METRICS_PATH
)
from backend.models.risk_classifier import HealthRiskClassifier
from backend.models.anomaly_detector import AnomalyDetector
from backend.analytics.feature_engineering import FEATURE_COLUMNS

client = TestClient(app)

def test_generate_robust_training_data():
    X, y = generate_robust_training_data(n_samples=500, random_state=42)
    assert X.shape[0] == 500
    assert X.shape[1] == len(FEATURE_COLUMNS)
    assert set(np.unique(y)) == {0, 1, 2}
    
    # Check physiological bounds (Heart rate in reasonable range)
    hr_col = X[:, 0]
    assert np.all(hr_col >= 40) and np.all(hr_col <= 200)

def test_train_and_evaluate_pipeline():
    metrics = train_and_evaluate_models(n_samples=600, random_state=42, save_models=True)
    
    assert metrics["status"] == "trained"
    assert "performance" in metrics
    perf = metrics["performance"]
    
    # Verify high accuracy and F1 score on clinical rules
    assert perf["test_accuracy"] >= 0.85
    assert perf["macro_f1"] >= 0.85
    assert perf["cv_5fold_mean_f1"] >= 0.85
    
    # Verify confusion matrix
    cm = metrics["confusion_matrix"]
    assert len(cm["classes"]) == 3
    assert len(cm["matrix"]) == 3
    
    # Verify file serialization
    assert os.path.exists(RF_MODEL_PATH)
    assert os.path.exists(ISO_MODEL_PATH)
    assert os.path.exists(METRICS_PATH)

def test_load_saved_models():
    rf_model, iso_model, metrics = load_saved_models()
    assert rf_model is not None
    assert iso_model is not None
    assert "performance" in metrics

def test_health_risk_classifier_with_saved_model():
    clf = HealthRiskClassifier()
    assert clf.is_trained is True
    metrics = clf.get_metrics()
    assert "performance" in metrics

def test_ml_api_status_endpoint():
    res = client.get("/api/ml/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "active"
    assert "supervised_risk_classifier" in data["models"]
    assert data["is_trained"] is True

def test_ml_api_metrics_endpoint():
    res = client.get("/api/ml/metrics")
    assert res.status_code == 200
    data = res.json()
    assert "performance" in data
    assert "confusion_matrix" in data
    assert "feature_importances" in data
    assert len(data["feature_importances"]) > 0

def test_ml_api_train_endpoint():
    res = client.post("/api/ml/train", json={"n_samples": 600, "random_state": 42})
    assert res.status_code == 200
    data = res.json()
    assert "Successfully trained" in data["message"]
    assert "metrics" in data
    assert data["metrics"]["performance"]["test_accuracy"] >= 0.85
