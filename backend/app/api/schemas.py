from typing import Optional
from uuid import UUID
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict


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
        from_attributes = True


# ---------- Deals ----------

class DealBase(BaseModel):
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    property_type: Optional[str] = None
    size_sqm: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    floor: Optional[int] = None
    asking_price: Optional[float] = None
    currency: Optional[str] = None
    url: Optional[str] = None
    broker_name: Optional[str] = None
    broker_contact: Optional[str] = None
    # Extended fields
    district: Optional[str] = None
    zone: Optional[str] = None
    condition: Optional[str] = None
    orientation: Optional[str] = None
    storage_room: Optional[bool] = False
    terrace: Optional[bool] = False
    balcony: Optional[bool] = False
    elevator: Optional[bool] = False
    garage: Optional[bool] = False
    listed_date: Optional[date] = None


class DealCreate(DealBase):
    message_id: Optional[UUID] = None  # null for portal-scraped deals


class DealRead(DealBase):
    id: UUID
    message_id: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Predictions ----------

class PredictRequest(BaseModel):
    deal_ids: list[UUID]


# ---------- Financial Analysis ----------

class FlipInput(BaseModel):
    deal_id: Optional[UUID] = None        # if set, name defaults to deal address
    name: Optional[str] = None            # required if deal_id is None
    size_sqm: float
    purchase_price: float
    capex_total: float
    capex_months: int
    project_months: int
    exit_price_per_sqm: float
    monthly_opex: float                   # utilities + community fees
    ibi_annual: float
    closing_costs_pct: float = 0.075      # ITP + notario + AJD + lawyers (default 7.5%)
    broker_fee_pct: float = 0.0363        # exit broker fee incl. VAT
    tax_rate: float = 0.0
    # Debt / leverage
    mortgage_ltv: float = 0.0            # e.g. 0.60 for 60% LTV
    mortgage_rate_annual: float = 0.0    # e.g. 0.067 for 6.7%
    capex_debt: float = 0.0              # portion of capex financed by debt
    capex_debt_rate_annual: float = 0.0


class FlipResult(BaseModel):
    id: UUID
    deal_id: Optional[UUID] = None
    name: str
    # Inputs (echoed back)
    size_sqm: float
    purchase_price: float
    capex_total: float
    project_months: int
    exit_price_per_sqm: float
    mortgage_ltv: float
    mortgage_rate_annual: float
    capex_debt: float
    # Outputs
    irr: Optional[float] = None
    moic: float
    return_on_equity: float
    gross_margin: float
    profit: float
    gross_exit_price: float
    net_exit_price: float
    total_dev_cost: float
    max_equity_exposure: float
    closing_costs: float
    broker_fee: float
    mortgage_debt: float
    total_debt: float
    created_at: datetime

    class Config:
        from_attributes = True


class PredictionRead(BaseModel):
    id: UUID
    deal_id: UUID
    predicted_price: float
    model_version: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PredictionWithDeal(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    deal_id: str
    predicted_price: float
    model_version: Optional[str] = None
    created_at: datetime
    address: Optional[str] = None
    district: Optional[str] = None
    size_sqm: Optional[float] = None
    asking_price: Optional[float] = None
    condition: Optional[str] = None
    url: Optional[str] = None
