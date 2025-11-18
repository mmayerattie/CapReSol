import uuid
from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Text,
    DateTime,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# Messages data schema
class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel = Column(String, nullable=False)          # gmail, whatsapp, portal
    source_id = Column(String)                        # email id, msg id, url
    sender = Column(String)
    received_at = Column(DateTime)
    raw_subject = Column(Text)
    raw_body_text = Column(Text)
    raw_body_html = Column(Text)
    attachment_urls = Column(JSONB)
    created_at = Column(DateTime, server_default=func.now())

    deal = relationship("Deal", back_populates="message", uselist=False)

class Deal(Base):
    __tablename__ = "deals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"))
    address = Column(Text)
    city = Column(Text)
    country = Column(Text)
    property_type = Column(Text)
    size_sqm = Column(Float)
    bedrooms = Column(Integer)
    bathrooms = Column(Integer)
    floor = Column(Integer)
    asking_price = Column(Float)
    currency = Column(String)
    url = Column(Text)
    broker_name = Column(Text)
    broker_contact = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    message = relationship("Message", back_populates="deal")
    prediction = relationship("Prediction", back_populates="deal", uselist=False)

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id = Column(UUID(as_uuid=True), ForeignKey("deals.id"), nullable=False)
    predicted_price = Column(Float, nullable=False)
    model_version = Column(String)
    created_at = Column(DateTime, server_default=func.now())

    deal = relationship("Deal", back_populates="prediction")