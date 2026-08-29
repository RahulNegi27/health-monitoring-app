import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.app.config import settings
from backend.app.database import engine, Base, SessionLocal
from backend.app.routes import health, simulator, user
from backend.app.models import SensorReading
from backend.services.simulator import simulator_instance
from backend.services.health_service import health_service

# Create database tables
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    db = SessionLocal()
    try:
        count = db.query(SensorReading).count()
        if count == 0:
            print("[INFO] Empty database detected. Seeding initial 7-day baseline health dataset...")
            samples = simulator_instance.generate_scenario_data(scenario="normal", days=7)
            health_service.ingest_sensor_readings(db, samples)
            print(f"[INFO] Successfully seeded {len(samples)} sensor readings.")
    except Exception as e:
        print(f"[WARN] Error seeding startup data: {e}")
    finally:
        db.close()
    
    yield
    # Shutdown logic (if any)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Full-stack Health Monitoring, Personal Baseline Tracking, and Anomaly Detection Application.",
    lifespan=lifespan
)

# Enable CORS for local development and web access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(health.router)
app.include_router(simulator.router)
app.include_router(user.router)

# Mount frontend directory for static assets
frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
def serve_index():
    index_file = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Health Monitoring API is running. Dashboard is at /static/index.html"}
