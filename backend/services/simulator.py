import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

class HealthDataSimulator:
    """
    Physiologically realistic sensor simulator generating multi-day time series
    and streaming real-time vitals for interactive demonstration.
    """
    def __init__(self):
        self.is_streaming = False
        self.current_scenario = "normal"
        self._stream_task: Optional[asyncio.Task] = None

    def generate_scenario_data(
        self, 
        scenario: str = "normal", 
        days: int = 7, 
        freq_minutes: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Generates realistic physiological time series data for specified scenario.
        """
        np.random.seed(42)
        readings = []
        start_time = datetime.utcnow() - timedelta(days=days)
        total_steps_in_sim = int((days * 24 * 60) / freq_minutes)

        # Base personal normal parameters
        base_resting_hr = 68.0
        base_temp = 36.6
        base_spo2 = 98.2

        for i in range(total_steps_in_sim):
            current_time = start_time + timedelta(minutes=i * freq_minutes)
            hour = current_time.hour
            minute = current_time.minute
            day_idx = int(i / ((24 * 60) / freq_minutes))

            # Circadian cycle factor (-1.0 at night, +1.0 during day)
            circadian = np.sin((hour - 6) / 24.0 * 2 * np.pi)

            # Default healthy profile for time of day
            if 0 <= hour < 7:
                # Sleeping
                activity = "Sleeping"
                steps = 0
                sleep_hours = round(min(8.0, hour + (minute / 60.0)), 1)
                is_resting = True
                hr = base_resting_hr - 6.0 + np.random.normal(0, 2.0)
                temp = base_temp - 0.3 + np.random.normal(0, 0.1)
                spo2 = base_spo2 + np.random.normal(0, 0.3)
            elif (7 <= hour < 9) or (17 <= hour < 19):
                # Active / Commute / Exercise
                activity = np.random.choice(["Walking", "Running"], p=[0.7, 0.3])
                steps = np.random.randint(400, 1800) if activity == "Walking" else np.random.randint(1800, 3500)
                sleep_hours = 7.5
                is_resting = False
                hr = (base_resting_hr + 25.0) if activity == "Walking" else (base_resting_hr + 60.0)
                hr += np.random.normal(0, 5.0)
                temp = base_temp + 0.2 + np.random.normal(0, 0.1)
                spo2 = base_spo2 - 0.4 + np.random.normal(0, 0.4)
            elif 9 <= hour < 17:
                # Working / Sedentary with light walks
                if np.random.rand() < 0.25:
                    activity = "Walking"
                    steps = np.random.randint(150, 600)
                    is_resting = False
                    hr = base_resting_hr + 12.0 + np.random.normal(0, 3.0)
                else:
                    activity = "Sedentary"
                    steps = 0
                    is_resting = True
                    hr = base_resting_hr + 4.0 + np.random.normal(0, 2.5)
                sleep_hours = 7.5
                temp = base_temp + np.random.normal(0, 0.1)
                spo2 = base_spo2 + np.random.normal(0, 0.3)
            else:
                # Evening relaxing
                activity = "Sedentary"
                steps = np.random.randint(0, 80)
                is_resting = (steps == 0)
                sleep_hours = 7.5
                hr = base_resting_hr + np.random.normal(0, 2.5)
                temp = base_temp + np.random.normal(0, 0.1)
                spo2 = base_spo2 + np.random.normal(0, 0.3)

            # Ingest Scenario Anomaly Modifiers
            if scenario == "fever" and day_idx >= (days - 3):
                # Fever progression in recent 3 days
                severity_factor = (day_idx - (days - 4)) / 3.0 # 0.33 to 1.0
                temp += (1.5 * severity_factor + np.random.normal(0, 0.2))
                hr += (28.0 * severity_factor + np.random.normal(0, 4.0))
                steps = int(steps * 0.2)
                sleep_hours = max(3.0, sleep_hours - 2.5)
                spo2 -= (1.5 * severity_factor)

            elif scenario == "stress" and day_idx >= (days - 4):
                # Chronic stress / severe sleep deprivation
                sleep_hours = max(3.5, 4.2 + np.random.normal(0, 0.4))
                hr += (14.0 + np.random.normal(0, 3.0))
                temp += 0.3
                if activity == "Sedentary":
                    hr += 8.0 # High HR while idle

            elif scenario == "hypoxia":
                # Intermittent nocturnal desaturation episodes
                if hour in [1, 2, 3, 4] and np.random.rand() < 0.6:
                    spo2 = float(np.random.uniform(84.0, 89.5))
                    hr += 22.0 # Hypoxia tachycardia arousal
                    is_resting = True

            elif scenario == "tachycardia":
                # Sudden idiopathic spikes during daytime sedentary hours
                if hour in [11, 15, 20] and minute == 0:
                    hr = float(np.random.uniform(130.0, 160.0))
                    steps = 0
                    activity = "Sedentary"
                    is_resting = True

            # Bound physiologically
            hr = float(np.clip(hr, 40.0, 210.0))
            spo2 = float(np.clip(spo2, 75.0, 100.0))
            temp = float(np.clip(temp, 34.5, 41.5))
            sleep_hours = float(np.clip(sleep_hours, 0.0, 12.0))

            readings.append({
                "timestamp": current_time,
                "heart_rate": round(hr, 1),
                "steps": int(steps),
                "activity": activity,
                "sleep_hours": round(sleep_hours, 1),
                "spo2": round(spo2, 1),
                "temperature": round(temp, 1),
                "is_resting": bool(is_resting)
            })

        self.current_scenario = scenario
        return readings

    def generate_single_live_sample(self, scenario: str = "normal") -> Dict[str, Any]:
        """
        Generates 1 current real-time telemetry frame.
        """
        now = datetime.utcnow()
        hour = now.hour
        base_hr = 70.0
        base_temp = 36.6
        base_spo2 = 98.0
        
        # Determine current physiological activity
        if 0 <= hour < 6:
            activity = "Sleeping"
            steps = 0
            is_resting = True
            hr = base_hr - 8.0 + np.random.normal(0, 1.5)
        else:
            activity = np.random.choice(["Sedentary", "Walking"], p=[0.8, 0.2])
            steps = 0 if activity == "Sedentary" else np.random.randint(15, 50)
            is_resting = (activity == "Sedentary")
            hr = base_hr + (15.0 if activity == "Walking" else 0.0) + np.random.normal(0, 2.0)

        temp = base_temp + np.random.normal(0, 0.08)
        spo2 = base_spo2 + np.random.normal(0, 0.2)
        sleep_hours = 7.2

        if scenario == "fever":
            temp += 1.8
            hr += 30.0
            sleep_hours = 4.0
        elif scenario == "stress":
            hr += 18.0
            sleep_hours = 4.5
        elif scenario == "hypoxia":
            spo2 = 88.5
            hr += 15.0
        elif scenario == "tachycardia":
            hr = 142.0
            activity = "Sedentary"
            steps = 0
            is_resting = True

        return {
            "timestamp": now,
            "heart_rate": round(float(np.clip(hr, 45, 200)), 1),
            "steps": int(steps),
            "activity": activity,
            "sleep_hours": round(sleep_hours, 1),
            "spo2": round(float(np.clip(spo2, 75, 100)), 1),
            "temperature": round(float(np.clip(temp, 35, 41)), 1),
            "is_resting": is_resting
        }

simulator_instance = HealthDataSimulator()
