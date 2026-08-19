# apps/api/app/services/matching_engine.py — finds nearest verified clinic offering a service for a given location
import logging
import math

from sqlalchemy.orm import Session

from app.models import Clinic

logger = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km between two lat/lng points (Haversine formula)."""
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def find_nearest_clinics(
    db: Session,
    lat: float,
    lng: float,
    service: str,
    limit: int = 3,
) -> list[Clinic]:
    """Return the nearest `limit` verified clinics that offer `service`.

    Filters:
    - verification_status == "verified"
    - the requested service appears in the clinic's `services` JSON list
      (case-insensitive); clinics with a null/empty services list are excluded.
    - lat/lng present (clinics with missing coordinates are excluded — expected,
      since geocoding is not wired up yet).

    Distance is computed in plain Python with the Haversine formula. This is
    correct and sufficient at current clinic volume; PostGIS (ST_Distance on
    PostGIS geometry columns) is the planned optimization once volume is large.
    """
    service_lower = service.strip().lower()
    verified = db.query(Clinic).filter(Clinic.verification_status == "verified").all()

    matches: list[tuple[float, Clinic]] = []
    for clinic in verified:
        services = clinic.services or []
        if not services:
            logger.debug("Clinic %s (%s) excluded: no services list", clinic.id, clinic.name)
            continue
        if service_lower not in [s.lower() for s in services]:
            logger.debug("Clinic %s (%s) excluded: service '%s' not offered", clinic.id, clinic.name, service)
            continue
        if clinic.lat is None or clinic.lng is None:
            logger.debug("Clinic %s (%s) excluded: missing lat/lng (expected at current data stage)", clinic.id, clinic.name)
            continue
        distance = haversine_km(lat, lng, clinic.lat, clinic.lng)
        matches.append((distance, clinic))

    matches.sort(key=lambda item: item[0])
    return [clinic for _, clinic in matches[:limit]]
