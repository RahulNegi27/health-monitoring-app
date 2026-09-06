# 🫀 PulseGuard AI — Health Monitoring & Biometric Anomaly Detection System

> **A Full-Stack Health & Wellness Intelligence Platform** designed to ingest sensor telemetry (Heart Rate, Steps/Activity, Sleep Duration, Blood Oxygen $\text{SpO}_2$, and Body Temperature), calculate personalized baseline norms, extract physiological time-series features, and detect multi-parameter health anomalies using **hybrid dynamic Z-score rules + unsupervised Isolation Forest + supervised Random Forest ML classification**.

---

## 🌟 Overview & Purpose

Modern wearables provide continuous physiological telemetry, but raw numbers alone are difficult for individuals to interpret. **PulseGuard AI** bridges this gap by transforming raw sensor time series into actionable wellness insights:

* **Dynamic Personal Baselines**: Evaluates current vitals against the user's personal moving average ($\mu \pm 2\sigma$) rather than arbitrary static generic population cutoffs.
* **Hybrid Anomaly Detection**:
  * **Phase 1 — Rule-based & Z-score thresholding**: Captures acute clinical deviations (e.g. resting tachycardia, nocturnal $\text{SpO}_2$ desaturations, high fever).
  * **Phase 2 — Machine Learning (Isolation Forest & Random Forest)**: Detects subtle multivariate clusters and produces an explainable continuous Risk Index ($0-100$).
* **Wellness & Anomaly Framing**: Designed for pattern monitoring, early warning alerts, and lifestyle recommendations—  **not as a replacement for medical diagnosis**.

---

## 🏗️ System Architecture

```
                    ┌────────────────────────┐
                    │  Wearable / Phone /    │
                    │  Scenario Simulator    │
                    └───────────┬────────────┘
                                │ JSON Telemetry
                                ▼
                    ┌────────────────────────┐
                    │    FastAPI Backend     │
                    │    REST & Ingestion    │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │   ETL & Preprocessing  │
                    │ Missing data imputation │
                    │ Outlier clipping       │
                    │ Resting period tagging │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │  Feature Engineering   │
                    │  • HRV RMSSD proxy     │
                    │  • 7-day Z-scores      │
                    │  • Activity-HR ratio   │
                    │  • Sleep debt index    │
                    └───────────┬────────────┘
                                │
                ┌───────────────┴───────────────┐
                ▼                               ▼
      ┌────────────────────┐          ┌────────────────────┐
      │ Phase 1: Dynamic   │          │ Phase 2: ML Engine │
      │ Baseline Z-Scores  │          │ • Isolation Forest │
      │ & Clinical Rules   │          │ • Random Forest    │
      └─────────┬──────────┘          └─────────┬──────────┘
                │                               │
                └───────────────┬───────────────┘
                                ▼
                    ┌────────────────────────┐
                    │ Anomaly & Risk Service │
                    │ Risk Score (0-100)     │
                    │ Feature Contributions  │
                    │ Action Recommendations │
                    └───────────┬────────────┘
                                │
                ┌───────────────┴───────────────┐
                ▼                               ▼
      ┌────────────────────┐          ┌────────────────────┐
      │  SQLite Database   │          │ Web UI Dashboard   │
      │  SQLAlchemy ORM    │          │ Live Pulse Cards   │
      │                    │          │ Interactive Trends │
      │                    │          │ Scenario Injectors │
      └────────────────────┘          └────────────────────┘
```

---

## 🧮 Mathematical & Algorithmic Foundation

### 1. Dynamic Personal Baseline & Z-Score
Rather than flagging heart rate against a static population average ($60-100\text{ BPM}$), PulseGuard maintains a rolling 7-day baseline of resting periods:

$$\mu_{\text{rest}} = \frac{1}{N} \sum_{i=1}^N \text{HR}_{i,\text{rest}}$$

$$\sigma_{\text{rest}} = \sqrt{\frac{1}{N-1} \sum_{i=1}^N (\text{HR}_{i,\text{rest}} - \mu_{\text{rest}})^2}$$

The deviation $Z$-score is computed as:

$$Z_{\text{HR}} = \frac{\text{HR}_{\text{current}} - \mu_{\text{rest}}}{\sigma_{\text{rest}}}$$

* **Normal:** $|Z| \le 2.0$
* **Moderate Deviation:** $2.0 < |Z| \le 3.0$
* **Severe Anomaly:** $|Z| > 3.0$ or $\text{HR} \ge 100\text{ BPM (resting)}$

### 2. Heart Rate Variability (HRV) RMSSD Proxy
Measures short-term autonomic parasympathetic activity:

$$\text{RMSSD} = \sqrt{\frac{1}{M-1} \sum_{k=1}^{M-1} (\text{HR}_{k+1} - \text{HR}_k)^2}$$

### 3. Isolation Forest Anomaly Scoring
The unsupervised tree ensemble measures how easily an instance $x$ is isolated by random partitioning:

$$s(x, n) = 2^{-\frac{\mathbb{E}(h(x))}{c(n)}}$$

Where $h(x)$ is path length and $c(n)$ is average path length of unsuccessful searches in a Binary Search Tree. Anomalous readings require significantly shorter paths to isolate.

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10+ (Tested with Python 3.13)
- Modern web browser (Chrome, Edge, Firefox, Safari)

### 2. Installation
Clone or navigate to the project directory:
```bash
cd d:/health
pip install -r requirements.txt
```

### 3. Run the Application
Start the FastAPI server:
```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser and navigate to:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

Interactive API Swagger documentation is available at:
👉 **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**

---

## 🧪 Interactive Scenario Playground

The dashboard includes 1-click preset scenario buttons to immediately demonstrate anomaly detection capabilities:

| Scenario | Physiological Simulation | Expected Detection |
| :--- | :--- | :--- |
| 🟢 **Normal Baseline** | 7-day healthy circadian curve, $7.5\text{h}$ sleep, $8\text{k}+$ steps. | **Low Risk (Score ~12/100)**, 0 active anomalies. |
| 🔴 **Infection / Fever** | Body temp rises to $38.8^\circ\text{C}$, resting HR rises $+30\text{ BPM}$, sleep drops to $3.5\text{h}$. | **High Risk (Score ~85/100)**, Severe Temperature & Tachycardia alerts. |
| 🟠 **Stress & Sleep Debt** | Chronic sleep deprivation ($<4.5\text{h}$), elevated sedentary HR during daytime work. | **Moderate Risk**, Sleep Debt & Activity/HR Decoupling alerts. |
| 🟣 **SpO₂ Hypoxia** | Nocturnal oxygen saturation dips to $84-89\%$ with tachycardia arousals. | **Severe SpO₂ Desaturation** & Nocturnal Hypoxia alerts. |
| ⚡ **Tachycardia Spike** | Sudden resting HR leap to $145\text{ BPM}$ with $0$ steps. | **Resting Tachycardia Anomaly** (Dynamic Z-score $+3.8\sigma$). |

---

## 📡 Real-Time Telemetry Streaming

Click the **"Live Stream: Off"** button in the top navigation bar to activate the real-time background emitter:
* Emits a new biometric sample every 3 seconds.
* Simulates live Bluetooth sensor synchronization from an Apple Watch, Garmin, or Fitbit.
* Watch the live heart rate badge, step progress, and trend graphs update dynamically.

---

## 🔬 API Reference

### Health & Vitals
- `GET /api/health/summary` — Today's vitals, baseline comparison, and active alerts.
- `GET /api/health/risk-score` — ML Random Forest Risk Assessment ($0-100$), classification tier, and explainable feature contributions.
- `GET /api/health/trends?days=7` — Time series for charting (High-res 48h timeline + Daily aggregations).
- `GET /api/health/anomalies` — List of detected anomalies with severity, detector type, and recommendations.
- `POST /api/health/anomalies/{id}/acknowledge` — Acknowledge an alert.
- `POST /api/health/ingest` — Ingest single or batch telemetry reading.

### Simulator & Baselines
- `POST /api/simulator/generate` — Generate multi-day preset health scenario dataset.
- `POST /api/simulator/stream/toggle` — Start/stop 3-second live sensor streaming.
- `GET /api/simulator/status` — Current streaming state and record count.
- `POST /api/simulator/reset` — Reset database to clean 7-day normal baseline.
- `GET /api/user/profile` & `PUT /api/user/profile` — Read/update personal baseline goals.

---

## 🎓 College Project / Presentation Highlights

If presenting this project for an evaluation:
1. **Explainable AI (XAI)**: Show how the Random Forest and Isolation Forest do not just output a binary label, but rank feature importances (e.g. Heart Rate Dynamics $35\%$, $\text{SpO}_2$ Desaturation $40\%$).
2. **Personalized vs Static Thresholds**: Explain why individual baselines ($\mu \pm 2\sigma$) are superior to static textbook ranges (an athlete's resting HR of $48\text{ BPM}$ is normal, whereas for another person it might be bradycardia).
3. **False Positive Suppression**: Discuss how multi-parameter confirmation (e.g. elevated HR without steps indicates stress/fever, whereas elevated HR with steps indicates healthy exercise) reduces alert fatigue.
4. **End-to-End Architecture**: Demonstrates data ingestion, automated cleaning/ETL, statistical feature engineering, machine learning modeling, REST API design, and modern interactive UI design.
