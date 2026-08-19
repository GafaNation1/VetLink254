# apps/api/app/schemas/match.py — Pydantic schema for matching-engine results (clinic + computed distance)
from app.schemas.clinic import ClinicResponse


class MatchResult(ClinicResponse):
    distance_km: float