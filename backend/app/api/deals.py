from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db import models
from app.api.schemas import DealRead, DealCreate
from app.services.extraction import create_deal_from_payload

router = APIRouter(prefix="/deals", tags=["deals"])

@router.get("/", response_model=List[DealRead])
def list_deals(db: Session = Depends(get_db)):
    return db.query(models.Deal).order_by(models.Deal.created_at.desc()).all()


@router.post("/from-message", response_model=DealRead)
def create_deal_from_message(payload: DealCreate, db: Session = Depends(get_db)):
    try:
        deal = create_deal_from_payload(db, payload)
        return deal
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))