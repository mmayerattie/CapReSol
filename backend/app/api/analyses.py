import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from fastapi import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db import models
from app.api.schemas import FlipInput, FlipResult
from app.utils.excel import run_flip_analysis

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.get("/", response_model=List[FlipResult])
def list_analyses(db: Session = Depends(get_db)):
    """Return all saved financial analyses, newest first."""
    return db.query(models.FinancialAnalysis).order_by(
        models.FinancialAnalysis.created_at.desc()
    ).all()


@router.post("/", response_model=FlipResult)
def create_analysis(payload: FlipInput, db: Session = Depends(get_db)):
    """
    Run Fix & Flip financial analysis and save to DB.

    If deal_id is provided, name defaults to the deal's address (override with name field).
    If no deal_id, name is required.
    """
    # Resolve name
    name = payload.name
    if payload.deal_id:
        deal = db.query(models.Deal).filter(models.Deal.id == payload.deal_id).first()
        if not deal:
            raise HTTPException(status_code=404, detail=f"Deal {payload.deal_id} not found")
        if not name:
            name = deal.address or str(payload.deal_id)
    else:
        if not name:
            raise HTTPException(status_code=422, detail="'name' is required when no deal_id is provided")

    # Run calculation
    result = run_flip_analysis(
        size_sqm=payload.size_sqm,
        purchase_price=payload.purchase_price,
        capex_total=payload.capex_total,
        capex_months=payload.capex_months,
        project_months=payload.project_months,
        exit_price_per_sqm=payload.exit_price_per_sqm,
        monthly_opex=payload.monthly_opex,
        ibi_annual=payload.ibi_annual,
        closing_costs_pct=payload.closing_costs_pct,
        broker_fee_pct=payload.broker_fee_pct,
        tax_rate=payload.tax_rate,
        mortgage_ltv=payload.mortgage_ltv,
        mortgage_rate_annual=payload.mortgage_rate_annual,
        capex_debt=payload.capex_debt,
        capex_debt_rate_annual=payload.capex_debt_rate_annual,
    )

    # Persist
    analysis = models.FinancialAnalysis(
        deal_id=payload.deal_id,
        name=name,
        size_sqm=payload.size_sqm,
        purchase_price=payload.purchase_price,
        capex_total=payload.capex_total,
        capex_months=payload.capex_months,
        project_months=payload.project_months,
        exit_price_per_sqm=payload.exit_price_per_sqm,
        monthly_opex=payload.monthly_opex,
        ibi_annual=payload.ibi_annual,
        closing_costs_pct=payload.closing_costs_pct,
        broker_fee_pct=payload.broker_fee_pct,
        tax_rate=payload.tax_rate,
        mortgage_ltv=payload.mortgage_ltv,
        mortgage_rate_annual=payload.mortgage_rate_annual,
        capex_debt=payload.capex_debt,
        capex_debt_rate_annual=payload.capex_debt_rate_annual,
        **result,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


@router.delete("/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: uuid.UUID, db: Session = Depends(get_db)):
    obj = db.query(models.FinancialAnalysis).filter(
        models.FinancialAnalysis.id == analysis_id
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Analysis not found")
    db.delete(obj)
    db.commit()
    return Response(status_code=204)


@router.put("/{analysis_id}", response_model=FlipResult)
def update_analysis(analysis_id: uuid.UUID, payload: FlipInput, db: Session = Depends(get_db)):
    obj = db.query(models.FinancialAnalysis).filter(
        models.FinancialAnalysis.id == analysis_id
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Analysis not found")

    name = payload.name
    if payload.deal_id:
        deal = db.query(models.Deal).filter(models.Deal.id == payload.deal_id).first()
        if not deal:
            raise HTTPException(status_code=404, detail=f"Deal {payload.deal_id} not found")
        if not name:
            name = deal.address or str(payload.deal_id)
    else:
        if not name:
            raise HTTPException(status_code=422, detail="'name' is required when no deal_id is provided")

    result = run_flip_analysis(
        size_sqm=payload.size_sqm,
        purchase_price=payload.purchase_price,
        capex_total=payload.capex_total,
        capex_months=payload.capex_months,
        project_months=payload.project_months,
        exit_price_per_sqm=payload.exit_price_per_sqm,
        monthly_opex=payload.monthly_opex,
        ibi_annual=payload.ibi_annual,
        closing_costs_pct=payload.closing_costs_pct,
        broker_fee_pct=payload.broker_fee_pct,
        tax_rate=payload.tax_rate,
        mortgage_ltv=payload.mortgage_ltv,
        mortgage_rate_annual=payload.mortgage_rate_annual,
        capex_debt=payload.capex_debt,
        capex_debt_rate_annual=payload.capex_debt_rate_annual,
    )

    obj.name = name
    obj.deal_id = payload.deal_id
    obj.size_sqm = payload.size_sqm
    obj.purchase_price = payload.purchase_price
    obj.capex_total = payload.capex_total
    obj.capex_months = payload.capex_months
    obj.project_months = payload.project_months
    obj.exit_price_per_sqm = payload.exit_price_per_sqm
    obj.monthly_opex = payload.monthly_opex
    obj.ibi_annual = payload.ibi_annual
    obj.closing_costs_pct = payload.closing_costs_pct
    obj.broker_fee_pct = payload.broker_fee_pct
    obj.tax_rate = payload.tax_rate
    obj.mortgage_ltv = payload.mortgage_ltv
    obj.mortgage_rate_annual = payload.mortgage_rate_annual
    obj.capex_debt = payload.capex_debt
    obj.capex_debt_rate_annual = payload.capex_debt_rate_annual
    for k, v in result.items():
        setattr(obj, k, v)

    db.commit()
    db.refresh(obj)
    return obj
