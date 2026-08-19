# apps/api/app/api/v1/clinics.py — Routers for GET list, GET one, POST create, and PATCH update Clinic endpoints
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_admin
from app.models import Clinic, User
from app.schemas import ClinicCreate, ClinicResponse, ClinicUpdate

router = APIRouter(prefix="/clinics", tags=["clinics"])

@router.get("/", response_model=list[ClinicResponse])
def list_clinics(db: Session = Depends(get_db)):
    return db.query(Clinic).all()

@router.get("/{clinic_id}", response_model=ClinicResponse)
def get_clinic(clinic_id: int, db: Session = Depends(get_db)):
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")
    return clinic

@router.post("/", response_model=ClinicResponse, status_code=201)
def create_clinic(payload: ClinicCreate, db: Session = Depends(get_db)):
    clinic = Clinic(**payload.model_dump())
    db.add(clinic)
    db.commit()
    db.refresh(clinic)
    return clinic

@router.patch("/{clinic_id}", response_model=ClinicResponse)
def update_clinic(
    clinic_id: int,
    payload: ClinicUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    for field, value in updates.items():
        setattr(clinic, field, value)
    db.commit()
    db.refresh(clinic)
    return clinic
