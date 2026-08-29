from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from backend.app.database import get_db
from backend.app.models import UserProfile
from backend.app.schemas import UserProfileOut, UserProfileUpdate
from backend.services.health_service import health_service

router = APIRouter(prefix="/api/user", tags=["User Profile & Baseline"])

@router.get("/profile", response_model=UserProfileOut)
def get_user_profile(db: Session = Depends(get_db)):
    """
    Returns user profile and configured baseline vitals.
    """
    return health_service.get_or_create_user_profile(db)

@router.put("/profile", response_model=UserProfileOut)
def update_user_profile(profile_data: UserProfileUpdate, db: Session = Depends(get_db)):
    """
    Updates user personal baseline and threshold preferences.
    """
    profile = health_service.get_or_create_user_profile(db)
    
    if profile_data.resting_hr_mean is not None:
        profile.resting_hr_mean = profile_data.resting_hr_mean
    if profile_data.resting_hr_std is not None:
        profile.resting_hr_std = profile_data.resting_hr_std
    if profile_data.target_steps is not None:
        profile.target_steps = profile_data.target_steps
    if profile_data.target_sleep is not None:
        profile.target_sleep = profile_data.target_sleep
    if profile_data.normal_spo2_min is not None:
        profile.normal_spo2_min = profile_data.normal_spo2_min
    if profile_data.normal_temp_mean is not None:
        profile.normal_temp_mean = profile_data.normal_temp_mean

    profile.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)
    return profile
