from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


# ---------- Messages ----------

class MessageBase(BaseModel):
    channel: str
    source_id: Optional[str] = None
    sender: Optional[str] = None
    raw_subject: Optional[str] = None
    raw_body_text: Optional[str] = None


class MessageCreate(MessageBase):
    pass


class MessageRead(MessageBase):
    id: UUID
    received_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True  # pydantic v2 (alias of orm_mode=True)


# ---------- Deals ----------

class DealRead(BaseModel):
    id: UUID
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    asking_price: Optional[float] = None
    currency: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class DealCreate(BaseModel):
    message_id: UUID
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    property_type: Optional[str] = None
    size_sqm: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    asking_price: Optional[float] = None
    currency: Optional[str] = None
    url: Optional[str] = None
    broker_name: Optional[str] = None
    broker_contact: Optional[str] = None