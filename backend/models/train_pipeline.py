import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, List
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    accuracy_score, 
    precision_recall_fscore_support, 
    confusion_matrix, 
    classification_report
)

from backend.analytics.feature_engineering import FEATURE_COLUMNS, prepare_feature_matrix

# Storage path for serialized models and metadata
MODEL_DIR = os.path.join(os.path.dirname(__file__), "saved_models")
RF_MODEL_PATH = os.path.join(MODEL_DIR, "random_forest_risk.joblib")
ISO_MODEL_PATH = os.path.join(MODEL_DIR, "isolation_forest.joblib")
METRICS_PATH = os.path.join(MODEL_DIR, "model_metrics.json")

CLASS_NAMES = ["Low", "Moderate", "High"]

def generate_robust_training_data(
    n_samples: int = 3000, 
    random_state: int = 42
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generates a physiologically and clinically grounded multi-class dataset.
    Features:
    [heart_rate, hr_std_7d, hrv_rmssd_proxy, hr_zscore, steps, sleep_hours, 
     spo2, spo2_drop, temperature, temp_diff, is_elevated_sedentary]
    
    Classes:
    0 = Low Risk (Normal healthy physiological homeostasis)
    1 = Moderate Risk (Mild fever, sub-optimal SpO2, sleep debt, stress decoupling)
    2 = High Risk (Acute fever, hypoxia desaturation, severe tachycardia)
    """
    rng = np.random.default_rng(random_state)

    # Class distribution: 55% Low, 28% Moderate, 17% High
    n_low = int(n_samples * 0.55)
    n_mod = int(n_samples * 0.28)
    n_high = n_samples - n_low - n_mod

    # 1. Low Risk (Healthy Baseline)
    hr_low = rng.normal(68.0, 5.0, n_low).clip(52.0, 84.0)
    hr_std_low = rng.uniform(2.0, 4.5, n_low)
    hrv_low = rng.uniform(30.0, 65.0, n_low)
    hr_z_low = (hr_low - 70.0) / 6.0
    steps_low = rng.integers(5000, 14000, n_low)
    sleep_low = rng.normal(7.6, 0.6, n_low).clip(6.5, 9.5)
    spo2_low = rng.uniform(96.5, 99.8, n_low)
    spo2_drop_low = np.zeros(n_low)
    temp_low = rng.normal(36.6, 0.15, n_low).clip(36.3, 37.1)
    temp_diff_low = temp_low - 36.6
    elev_sed_low = np.zeros(n_low)

    X_low = np.column_stack([
        hr_low, hr_std_low, hrv_low, hr_z_low, steps_low, sleep_low,
        spo2_low, spo2_drop_low, temp_low, temp_diff_low, elev_sed_low
    ])
    y_low = np.zeros(n_low, dtype=int)

    # 2. Moderate Risk (Stress, fatigue, mild fever, borderline oxygen)
    hr_mod = rng.normal(88.0, 7.0, n_mod).clip(76.0, 106.0)
    hr_std_mod = rng.uniform(3.5, 9.0, n_mod)
    hrv_mod = rng.uniform(14.0, 32.0, n_mod)
    hr_z_mod = (hr_mod - 70.0) / 6.0
    steps_mod = rng.integers(1200, 5500, n_mod)
    sleep_mod = rng.normal(5.2, 0.8, n_mod).clip(4.0, 6.4)
    spo2_mod = rng.uniform(93.0, 95.8, n_mod)
    spo2_drop_mod = np.maximum(0.0, 95.0 - spo2_mod)
    temp_mod = rng.normal(37.6, 0.25, n_mod).clip(37.2, 38.1)
    temp_diff_mod = temp_mod - 36.6
    elev_sed_mod = rng.choice([0, 1], size=n_mod, p=[0.35, 0.65])

    X_mod = np.column_stack([
        hr_mod, hr_std_mod, hrv_mod, hr_z_mod, steps_mod, sleep_mod,
        spo2_mod, spo2_drop_mod, temp_mod, temp_diff_mod, elev_sed_mod
    ])
    y_mod = np.ones(n_mod, dtype=int)

    # 3. High Risk (Acute tachycardia, high fever, hypoxia)
    hr_high = rng.normal(118.0, 14.0, n_high).clip(98.0, 160.0)
    hr_std_high = rng.uniform(6.5, 16.0, n_high)
    hrv_high = rng.uniform(4.0, 18.0, n_high)
    hr_z_high = (hr_high - 70.0) / 6.0
    steps_high = rng.integers(100, 2000, n_high)
    sleep_high = rng.normal(3.8, 0.9, n_high).clip(1.5, 4.8)
    spo2_high = rng.uniform(84.0, 92.5, n_high)
    spo2_drop_high = np.maximum(0.0, 95.0 - spo2_high)
    temp_high = rng.normal(38.8, 0.5, n_high).clip(38.2, 40.5)
    temp_diff_high = temp_high - 36.6
    elev_sed_high = rng.choice([0, 1], size=n_high, p=[0.1, 0.9])

    X_high = np.column_stack([
        hr_high, hr_std_high, hrv_high, hr_z_high, steps_high, sleep_high,
        spo2_high, spo2_drop_high, temp_high, temp_diff_high, elev_sed_high
    ])
    y_high = np.full(n_high, 2, dtype=int)

    X = np.vstack([X_low, X_mod, X_high])
    y = np.concatenate([y_low, y_mod, y_high])

    # Add subtle realistic measurement noise (1% gaussian perturbation)
    noise = rng.normal(0, 0.01, size=X.shape) * np.std(X, axis=0, keepdims=True)
    X = X + noise

    return X, y

def train_and_evaluate_models(
    n_samples: int = 3000,
    random_state: int = 42,
    save_models: bool = True
) -> Dict[str, Any]:
    """
    Executes the end-to-end ML model training pipeline:
    1. Generates stratified clinical physiological dataset.
    2. Performs Train/Validation/Test split (70% train, 15% val, 15% test).
    3. Trains Supervised Random Forest Classifier with cross-validation.
    4. Trains Unsupervised Isolation Forest Anomaly Detector.
    5. Evaluates comprehensive test metrics (Accuracy, F1, Confusion Matrix, Feature Importance).
    6. Serializes model weights to disk for instant application startup.
    """
    os.makedirs(MODEL_DIR, exist_ok=True)

    # 1. Dataset Generation
    X, y = generate_robust_training_data(n_samples=n_samples, random_state=random_state)
    
    # Train / Test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=random_state, stratify=y
    )

    # 2. Supervised Random Forest Risk Model
    rf_model = RandomForestClassifier(
        n_estimators=120,
        max_depth=8,
        min_samples_split=4,
        min_samples_leaf=2,
        random_state=random_state,
        n_jobs=-1
    )

    # 5-fold Cross-validation on training data
    cv_scores = cross_val_score(rf_model, X_train, y_train, cv=5, scoring="f1_macro")
    rf_model.fit(X_train, y_train)

    # Evaluation on held-out test set
    y_pred = rf_model.predict(X_test)
    test_accuracy = float(accuracy_score(y_test, y_pred))
    precision_macro, recall_macro, f1_macro, _ = precision_recall_fscore_support(
        y_test, y_pred, average="macro", zero_division=0
    )
    precision_weighted, recall_weighted, f1_weighted, _ = precision_recall_fscore_support(
        y_test, y_pred, average="weighted", zero_division=0
    )

    # Per-class metrics
    per_class_p, per_class_r, per_class_f1, per_class_supp = precision_recall_fscore_support(
        y_test, y_pred, average=None, zero_division=0
    )

    class_metrics = {}
    for idx, cname in enumerate(CLASS_NAMES):
        class_metrics[cname] = {
            "precision": round(float(per_class_p[idx]), 4),
            "recall": round(float(per_class_r[idx]), 4),
            "f1_score": round(float(per_class_f1[idx]), 4),
            "test_support": int(per_class_supp[idx])
        }

    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred).tolist()

    # Feature importances
    importances = rf_model.feature_importances_
    feature_importance_list = []
    for col, imp in sorted(zip(FEATURE_COLUMNS, importances), key=lambda x: x[1], reverse=True):
        feature_importance_list.append({
            "feature": col,
            "importance": round(float(imp), 4),
            "percentage": round(float(imp) * 100, 2)
        })

    # 3. Unsupervised Isolation Forest Model
    # Fit primarily on normal/low-risk physiological data with controlled contamination
    X_train_normal = X_train[y_train == 0]
    iso_model = IsolationForest(
        n_estimators=100,
        contamination=0.06,
        random_state=random_state,
        n_jobs=-1
    )
    iso_model.fit(X_train_normal)

    # Isolation forest test evaluation
    iso_test_preds = iso_model.predict(X_test) # -1 is anomaly, 1 is normal
    # In test set, y_test == 2 (high risk) should largely be flagged as -1
    high_risk_detected = int(np.sum((y_test == 2) & (iso_test_preds == -1)))
    high_risk_total = int(np.sum(y_test == 2))
    high_risk_sensitivity = round(high_risk_detected / max(1, high_risk_total), 4)

    # 4. Metric Summary Bundle
    now_str = datetime.now(timezone.utc).isoformat()
    metrics_bundle = {
        "status": "trained",
        "trained_at": now_str,
        "sample_counts": {
            "total_samples": len(X),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "class_distribution": {
                "Low": int(np.sum(y == 0)),
                "Moderate": int(np.sum(y == 1)),
                "High": int(np.sum(y == 2))
            }
        },
        "performance": {
            "test_accuracy": round(test_accuracy, 4),
            "macro_f1": round(float(f1_macro), 4),
            "macro_precision": round(float(precision_macro), 4),
            "macro_recall": round(float(recall_macro), 4),
            "weighted_f1": round(float(f1_weighted), 4),
            "cv_5fold_mean_f1": round(float(np.mean(cv_scores)), 4),
            "cv_5fold_std": round(float(np.std(cv_scores)), 4),
            "isolation_forest_high_risk_sensitivity": high_risk_sensitivity
        },
        "class_breakdown": class_metrics,
        "confusion_matrix": {
            "classes": CLASS_NAMES,
            "matrix": cm
        },
        "feature_importances": feature_importance_list,
        "hyperparameters": {
            "rf_n_estimators": rf_model.n_estimators,
            "rf_max_depth": rf_model.max_depth,
            "iso_contamination": iso_model.contamination
        }
    }

    # 5. Serialization
    if save_models:
        joblib.dump(rf_model, RF_MODEL_PATH)
        joblib.dump(iso_model, ISO_MODEL_PATH)
        with open(METRICS_PATH, "w", encoding="utf-8") as f:
            json.dump(metrics_bundle, f, indent=2)
        print(f"[ML PIPELINE] Successfully serialized models to {MODEL_DIR}")

    return metrics_bundle

def load_saved_models() -> Tuple[Any, Any, Dict[str, Any]]:
    """
    Loads pre-trained model artifacts and metrics from disk.
    Returns (rf_model, iso_model, metrics_bundle) or (None, None, None).
    """
    if os.path.exists(RF_MODEL_PATH) and os.path.exists(ISO_MODEL_PATH):
        try:
            rf_model = joblib.load(RF_MODEL_PATH)
            iso_model = joblib.load(ISO_MODEL_PATH)
            metrics = {}
            if os.path.exists(METRICS_PATH):
                with open(METRICS_PATH, "r", encoding="utf-8") as f:
                    metrics = json.load(f)
            return rf_model, iso_model, metrics
        except Exception as e:
            print(f"[WARN] Failed loading saved models: {e}")
    return None, None, None
