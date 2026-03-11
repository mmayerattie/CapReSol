import uuid
from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Text,
    DateTime,
    Date,
    Boolean,
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
    url = Column(Text, unique=True)
    broker_name = Column(Text)
    broker_contact = Column(Text)
    # Extended fields for ML and scraping
    district = Column(Text)
    zone = Column(Text)
    condition = Column(Text)
    orientation = Column(Text)
    storage_room = Column(Boolean, default=False)
    terrace = Column(Boolean, default=False)
    balcony = Column(Boolean, default=False)
    elevator = Column(Boolean, default=False)
    garage = Column(Boolean, default=False)
    listed_date = Column(Date)
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


class FinancialAnalysis(Base):
    __tablename__ = "financial_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id = Column(UUID(as_uuid=True), ForeignKey("deals.id"), nullable=True)
    name = Column(Text, nullable=False)               # e.g. "Serrano 81" — auto or manual

    # Inputs
    size_sqm = Column(Float)
    purchase_price = Column(Float)
    capex_total = Column(Float)
    capex_months = Column(Integer)
    project_months = Column(Integer)
    exit_price_per_sqm = Column(Float)
    monthly_opex = Column(Float)
    ibi_annual = Column(Float)
    closing_costs_pct = Column(Float)
    broker_fee_pct = Column(Float)
    tax_rate = Column(Float, default=0.0)
    # Debt inputs
    mortgage_ltv = Column(Float, default=0.0)
    mortgage_rate_annual = Column(Float, default=0.0)
    capex_debt = Column(Float, default=0.0)
    capex_debt_rate_annual = Column(Float, default=0.0)

    # Outputs
    irr = Column(Float)
    moic = Column(Float)
    return_on_equity = Column(Float)
    gross_margin = Column(Float)
    profit = Column(Float)
    gross_exit_price = Column(Float)
    net_exit_price = Column(Float)
    total_dev_cost = Column(Float)
    max_equity_exposure = Column(Float)
    closing_costs = Column(Float)
    broker_fee = Column(Float)
    mortgage_debt = Column(Float)
    total_debt = Column(Float)

    created_at = Column(DateTime, server_default=func.now())