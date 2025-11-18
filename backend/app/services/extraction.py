from sqlalchemy.orm import Session
from uuid import UUID

from app.db import models
from app.api.schemas import DealCreate


def create_deal_from_payload(db: Session, payload: DealCreate) -> models.Deal:
    # Ensure the message exists (basic safety)
    message = db.query(models.Message).filter(models.Message.id == payload.message_id).first()
    if not message:
        raise ValueError("Message not found")

    deal = models.Deal(
        message_id=payload.message_id,
        address=payload.address,
        city=payload.city,
        country=payload.country,
        property_type=payload.property_type,
        size_sqm=payload.size_sqm,
        bedrooms=payload.bedrooms,
        bathrooms=payload.bathrooms,
        asking_price=payload.asking_price,
        currency=payload.currency,
        url=payload.url,
        broker_name=payload.broker_name,
        broker_contact=payload.broker_contact,
    )

    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal