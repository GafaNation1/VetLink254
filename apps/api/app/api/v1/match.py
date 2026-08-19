# apps/api/app/api/v1/match.py — Router for GET /match, nearest verified clinic matching by location and service
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import ClinicResponse, MatchResult
from app.services.matching_engine import find_nearest_clinics, haversine_km

router = APIRouter(prefix="/match", tags=["match"])


@router.get("/", response_model=List[MatchResult])
def match_clinics(
    lat: float = Query(..., description="User latitude"),
    lng: float = Query(..., description="User longitude"),
    service: str = Query(..., description="Service category to match, e.g. consultation"),
    limit: int = Query(3, ge=1, le=20, description="Max clinics to return"),
    db: Session = Depends(get_db),
):
    clinics = find_nearest_clinics(db, lat, lng, service, limit=limit)
    results = []
    for clinic in clinics:
        clinic_data = ClinicResponse.model_validate(clinic).model_dump()
        clinic_data["distance_km"] = round(haversine_km(lat, lng, clinic.lat, clinic.lng), 3)
        results.append(MatchResult(**clinic_data))
    return results