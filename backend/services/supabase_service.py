import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import httpx

from backend.app.config import settings

class SupabaseService:
    """
    Manages cloud integration with Supabase.
    Supports Supabase PostgREST API over HTTPX (syncing sensor readings and anomaly alerts)
    as well as status checks, connection tests, and SQL migration scripts.
    """
    def __init__(self):
        self.url = settings.SUPABASE_URL.rstrip("/") if settings.SUPABASE_URL else ""
        self.key = settings.SUPABASE_KEY or settings.SUPABASE_SERVICE_ROLE_KEY or ""
        self.last_sync_time: Optional[str] = None
        self.last_sync_count: int = 0
        self.last_status: str = "unconfigured" if not self.url or not self.key else "configured"

    def update_credentials(self, url: str, key: str, save_to_env: bool = True):
        """
        Updates credentials at runtime and optionally persists to .env file.
        """
        self.url = url.rstrip("/")
        self.key = key
        self.last_status = "configured" if self.url and self.key else "unconfigured"

        if save_to_env:
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
            try:
                env_lines = []
                if os.path.exists(env_path):
                    with open(env_path, "r", encoding="utf-8") as f:
                        env_lines = f.readlines()
                
                new_lines = []
                url_written = False
                key_written = False
                for line in env_lines:
                    if line.startswith("SUPABASE_URL="):
                        new_lines.append(f'SUPABASE_URL="{self.url}"\n')
                        url_written = True
                    elif line.startswith("SUPABASE_KEY="):
                        new_lines.append(f'SUPABASE_KEY="{self.key}"\n')
                        key_written = True
                    else:
                        new_lines.append(line)
                
                if not url_written:
                    new_lines.append(f'SUPABASE_URL="{self.url}"\n')
                if not key_written:
                    new_lines.append(f'SUPABASE_KEY="{self.key}"\n')

                with open(env_path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
            except Exception as e:
                print(f"[WARN] Could not write to .env: {e}")

    def _get_headers(self, key_override: Optional[str] = None) -> Dict[str, str]:
        active_key = key_override or self.key
        return {
            "apikey": active_key,
            "Authorization": f"Bearer {active_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

    def test_connection(self, url: Optional[str] = None, key: Optional[str] = None) -> Dict[str, Any]:
        """
        Pings the Supabase REST/Auth endpoint to verify connectivity and credentials.
        """
        test_url = (url or self.url).rstrip("/")
        test_key = key or self.key

        if not test_url or not test_key:
            return {
                "success": False,
                "status": "not_configured",
                "message": "Supabase Project URL and API Key are required.",
                "url": test_url
            }

        headers = self._get_headers(key_override=test_key)
        
        # Test endpoint: Supabase REST root OpenAPI specification or Auth health check
        try:
            with httpx.Client(timeout=6.0) as client:
                # 1. Try REST endpoint
                resp = client.get(f"{test_url}/rest/v1/", headers=headers)
                if resp.status_code in [200, 204]:
                    self.last_status = "connected"
                    return {
                        "success": True,
                        "status": "connected",
                        "message": "Successfully connected to Supabase PostgREST endpoint!",
                        "url": test_url,
                        "status_code": resp.status_code
                    }
                elif resp.status_code == 401 or resp.status_code == 403:
                    return {
                        "success": False,
                        "status": "auth_error",
                        "message": "Connection reached Supabase, but API Key authentication failed (401/403).",
                        "url": test_url,
                        "status_code": resp.status_code
                    }
                
                # 2. Try Auth health endpoint as fallback
                auth_resp = client.get(f"{test_url}/auth/v1/health")
                if auth_resp.status_code == 200:
                    self.last_status = "connected"
                    return {
                        "success": True,
                        "status": "connected",
                        "message": "Supabase instance reached successfully (Auth service online).",
                        "url": test_url,
                        "status_code": 200
                    }

                return {
                    "success": False,
                    "status": "warning",
                    "message": f"Supabase responded with HTTP {resp.status_code}: {resp.text[:120]}",
                    "url": test_url,
                    "status_code": resp.status_code
                }
        except httpx.ConnectError:
            return {
                "success": False,
                "status": "network_error",
                "message": f"Could not resolve or connect to host {test_url}. Verify the URL spelling.",
                "url": test_url
            }
        except Exception as e:
            return {
                "success": False,
                "status": "error",
                "message": f"Connection test failed: {str(e)}",
                "url": test_url
            }

    def sync_readings_to_supabase(self, readings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Uploads local sensor readings to Supabase 'sensor_readings' table.
        """
        if not self.url or not self.key:
            return {"success": False, "message": "Supabase is not configured.", "synced": 0}

        if not readings:
            return {"success": True, "message": "No readings to sync.", "synced": 0}

        headers = self._get_headers()
        # Clean formatting for Supabase
        payload = []
        for r in readings:
            ts = r.get("timestamp")
            if isinstance(ts, datetime):
                ts_str = ts.isoformat()
            else:
                ts_str = str(ts)

            payload.append({
                "timestamp": ts_str,
                "heart_rate": float(r.get("heart_rate", 70.0)),
                "steps": int(r.get("steps", 0)),
                "activity": str(r.get("activity", "Sedentary")),
                "sleep_hours": float(r.get("sleep_hours", 0.0)),
                "spo2": float(r.get("spo2", 98.0)),
                "temperature": float(r.get("temperature", 36.6)),
                "is_resting": bool(r.get("is_resting", False))
            })

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    f"{self.url}/rest/v1/sensor_readings",
                    headers=headers,
                    json=payload
                )
                if resp.status_code in [200, 201, 204]:
                    self.last_sync_time = datetime.now(timezone.utc).isoformat()
                    self.last_sync_count = len(payload)
                    return {
                        "success": True,
                        "message": f"Successfully synced {len(payload)} sensor readings to Supabase.",
                        "synced": len(payload)
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Supabase responded with HTTP {resp.status_code}: {resp.text[:150]}",
                        "synced": 0
                    }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed syncing to Supabase: {str(e)}",
                "synced": 0
            }

    def sync_anomalies_to_supabase(self, alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Uploads detected anomaly alerts to Supabase 'anomaly_alerts' table.
        """
        if not self.url or not self.key or not alerts:
            return {"success": False, "message": "Supabase unconfigured or no alerts.", "synced": 0}

        headers = self._get_headers()
        payload = []
        for a in alerts:
            ts = a.get("timestamp")
            ts_str = ts.isoformat() if isinstance(ts, datetime) else str(ts)

            payload.append({
                "timestamp": ts_str,
                "parameter": str(a.get("parameter", "Vitals")),
                "metric_value": float(a.get("metric_value", 0.0)),
                "baseline_value": float(a.get("baseline_value", 0.0)) if a.get("baseline_value") is not None else None,
                "deviation_zscore": float(a.get("deviation_zscore", 0.0)) if a.get("deviation_zscore") is not None else None,
                "severity": str(a.get("severity", "moderate")),
                "detector_type": str(a.get("detector_type", "rule")),
                "explanation": str(a.get("explanation", "")),
                "recommendation": str(a.get("recommendation", "")),
                "is_acknowledged": bool(a.get("is_acknowledged", False))
            })

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    f"{self.url}/rest/v1/anomaly_alerts",
                    headers=headers,
                    json=payload
                )
                if resp.status_code in [200, 201, 204]:
                    return {
                        "success": True,
                        "message": f"Synced {len(payload)} anomaly alerts to Supabase.",
                        "synced": len(payload)
                    }
                return {
                    "success": False,
                    "message": f"HTTP {resp.status_code}: {resp.text[:120]}",
                    "synced": 0
                }
        except Exception as e:
            return {"success": False, "message": str(e), "synced": 0}

    def get_status(self) -> Dict[str, Any]:
        is_config = bool(self.url and self.key)
        masked_key = ""
        if self.key:
            masked_key = self.key[:6] + "..." + self.key[-4:] if len(self.key) > 10 else "***"

        return {
            "is_configured": is_config,
            "status": "connected" if is_config else "unconfigured",
            "supabase_url": self.url or "Not configured",
            "has_key": bool(self.key),
            "masked_key": masked_key,
            "last_sync_time": self.last_sync_time,
            "last_sync_count": self.last_sync_count,
            "sync_enabled": settings.SUPABASE_SYNC_ENABLED,
            "auto_sync": settings.SUPABASE_AUTO_SYNC
        }

    def get_sql_migration(self) -> str:
        """
        Returns ready-to-run PostgreSQL schema script for Supabase SQL Editor.
        """
        return """-- =======================================================
-- PulseGuard AI — Supabase Database Migration Schema
-- Run this in your Supabase Project -> SQL Editor
-- =======================================================

-- 1. Sensor Telemetry Readings Table
CREATE TABLE IF NOT EXISTS public.sensor_readings (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    heart_rate DOUBLE PRECISION NOT NULL,
    steps INTEGER DEFAULT 0 NOT NULL,
    activity VARCHAR(50) DEFAULT 'Sedentary',
    sleep_hours DOUBLE PRECISION DEFAULT 0.0,
    spo2 DOUBLE PRECISION NOT NULL,
    temperature DOUBLE PRECISION DEFAULT 36.6,
    is_resting BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL
);

-- Index for fast time series lookups
CREATE INDEX IF NOT EXISTS idx_sensor_readings_timestamp 
ON public.sensor_readings (timestamp DESC);

-- 2. Anomaly Alerts Table
CREATE TABLE IF NOT EXISTS public.anomaly_alerts (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    parameter VARCHAR(50) NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    baseline_value DOUBLE PRECISION,
    deviation_zscore DOUBLE PRECISION,
    severity VARCHAR(20) DEFAULT 'moderate',
    detector_type VARCHAR(50) DEFAULT 'rule',
    explanation TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    is_acknowledged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_anomaly_alerts_timestamp 
ON public.anomaly_alerts (timestamp DESC);

-- 3. Daily Summary Aggregates Table
CREATE TABLE IF NOT EXISTS public.daily_aggregates (
    id BIGSERIAL PRIMARY KEY,
    date DATE UNIQUE NOT NULL,
    resting_hr DOUBLE PRECISION,
    avg_hr DOUBLE PRECISION,
    min_hr DOUBLE PRECISION,
    max_hr DOUBLE PRECISION,
    total_steps INTEGER DEFAULT 0,
    total_sleep DOUBLE PRECISION DEFAULT 0.0,
    avg_spo2 DOUBLE PRECISION,
    min_spo2 DOUBLE PRECISION,
    avg_temp DOUBLE PRECISION DEFAULT 36.6,
    anomaly_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL
);

-- Enable Row Level Security (RLS) & allow authenticated / public read & write
ALTER TABLE public.sensor_readings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.anomaly_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_aggregates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow anon insert & select sensor_readings" 
ON public.sensor_readings FOR ALL TO anon USING (true) WITH CHECK (true);

CREATE POLICY "Allow anon insert & select anomaly_alerts" 
ON public.anomaly_alerts FOR ALL TO anon USING (true) WITH CHECK (true);

CREATE POLICY "Allow anon insert & select daily_aggregates" 
ON public.daily_aggregates FOR ALL TO anon USING (true) WITH CHECK (true);
"""

# Singleton instance
supabase_service = SupabaseService()
