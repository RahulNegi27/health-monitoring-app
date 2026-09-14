"""
PulseGuard AI — Machine Learning Model Training & Evaluation CLI
Run directly: python train_models.py
"""

import sys
import json
from backend.models.train_pipeline import train_and_evaluate_models, CLASS_NAMES

def main():
    print("=" * 72)
    print("  PulseGuard AI — Biometric ML Training & Clinical Evaluation Pipeline  ")
    print("=" * 72)
    print("[1/4] Generating stratified physiological multi-parameter corpus (3,000 samples)...")
    print("[2/4] Training Supervised Random Forest Risk Classifier (120 trees, 5-fold CV)...")
    print("[3/4] Training Unsupervised Isolation Forest Anomaly Detector...")
    print("[4/4] Evaluating multi-class precision, recall, F1, and confusion matrix...")
    print("-" * 72)

    metrics = train_and_evaluate_models(n_samples=3000, random_state=42, save_models=True)

    perf = metrics["performance"]
    samples = metrics["sample_counts"]
    cm = metrics["confusion_matrix"]["matrix"]
    importances = metrics["feature_importances"]

    print(f"\n[RESULTS] Training Completed Successfully at {metrics['trained_at']}")
    print(f"Total Dataset Size: {samples['total_samples']} samples (Train: {samples['train_samples']}, Test: {samples['test_samples']})")
    print(f"Class Breakdown: Low={samples['class_distribution']['Low']} | Moderate={samples['class_distribution']['Moderate']} | High={samples['class_distribution']['High']}")
    print("-" * 72)
    print(f"  * Test Accuracy:       {perf['test_accuracy'] * 100:.2f}%")
    print(f"  * Macro F1-Score:      {perf['macro_f1'] * 100:.2f}%")
    print(f"  * Macro Precision:     {perf['macro_precision'] * 100:.2f}%")
    print(f"  * Macro Recall:        {perf['macro_recall'] * 100:.2f}%")
    print(f"  * 5-Fold CV Mean F1:   {perf['cv_5fold_mean_f1'] * 100:.2f}% (+/- {perf['cv_5fold_std'] * 100:.2f}%)")
    print(f"  * Isolation Forest High Risk Sensitivity: {perf['isolation_forest_high_risk_sensitivity'] * 100:.2f}%")
    print("-" * 72)

    print("\n[CONFUSION MATRIX] (Rows: Actual, Columns: Predicted)")
    print(f"{'':>12} | {'Pred: Low':>10} | {'Pred: Mod':>10} | {'Pred: High':>10} |")
    print("-" * 52)
    for i, row_name in enumerate(CLASS_NAMES):
        row = cm[i]
        print(f"{'Act: ' + row_name:>12} | {row[0]:>10} | {row[1]:>10} | {row[2]:>10} |")

    print("\n[TOP 5 CLINICAL FEATURE IMPORTANCES]")
    for idx, item in enumerate(importances[:5], 1):
        print(f"  {idx}. {item['feature']:<25} : {item['percentage']:>5.1f}% contribution")

    print("\n" + "=" * 72)
    print("  Model artifacts saved to: backend/models/saved_models/")
    print("=" * 72 + "\n")

if __name__ == "__main__":
    main()
