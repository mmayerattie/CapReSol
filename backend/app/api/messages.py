from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db import models
from app.api.schemas import MessageCreate, MessageRead

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/", response_model=MessageRead)
def create_message(payload: MessageCreate, db: Session = Depends(get_db)):
    msg = models.Message(
        channel=payload.channel,
        source_id=payload.source_id,
        sender=payload.sender,
        raw_subject=payload.raw_subject,
        raw_body_text=payload.raw_body_text,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


@router.get("/", response_model=List[MessageRead])
def list_messages(db: Session = Depends(get_db)):
    return db.query(models.Message).order_by(models.Message.created_at.desc()).all()
