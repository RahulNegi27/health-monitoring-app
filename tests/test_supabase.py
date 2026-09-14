import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.services.supabase_service import supabase_service

client = TestClient(app)

def test_supabase_service_default_status():
    status = supabase_service.get_status()
    assert "is_configured" in status
    assert "status" in status
    assert "sync_enabled" in status

def test_supabase_schema_generation():
    sql = supabase_service.get_sql_migration()
    assert "CREATE TABLE IF NOT EXISTS public.sensor_readings" in sql
    assert "CREATE TABLE IF NOT EXISTS public.anomaly_alerts" in sql
    assert "CREATE TABLE IF NOT EXISTS public.daily_aggregates" in sql
    assert "ROW LEVEL SECURITY" in sql

def test_supabase_test_connection_unconfigured():
    res = supabase_service.test_connection(url="", key="")
    assert res["success"] is False
    assert res["status"] == "not_configured"

def test_supabase_test_connection_invalid_url():
    res = supabase_service.test_connection(url="https://invalid-non-existent-subdomain-12345.supabase.co", key="testkey")
    assert res["success"] is False
    assert res["status"] in ["network_error", "error"]

def test_supabase_api_status_endpoint():
    res = client.get("/api/supabase/status")
    assert res.status_code == 200
    data = res.json()
    assert "is_configured" in data
    assert "status" in data

def test_supabase_api_schema_endpoint():
    res = client.get("/api/supabase/schema")
    assert res.status_code == 200
    data = res.json()
    assert "sql" in data
    assert "sensor_readings" in data["sql"]

def test_supabase_api_test_endpoint():
    res = client.post("/api/supabase/test", json={"url": "https://test.supabase.co", "key": "abc"})
    assert res.status_code == 200
    data = res.json()
    assert "success" in data

def test_supabase_api_sync_unconfigured():
    # If unconfigured, sync should return a clean informative message without crashing
    res = client.post("/api/supabase/sync")
    assert res.status_code == 200
    data = res.json()
    assert "synced_readings" in data
    assert "synced_alerts" in data
