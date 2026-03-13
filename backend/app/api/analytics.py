from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Deal, Prediction, FinancialAnalysis

router = APIRouter()


@router.get("")
def get_analytics(
    db: Session = Depends(get_db),
    max_price_sqm: int = 25000,
    min_price_sqm: int = 500,
):
    # Outlier filter: exclude deals outside [min_price_sqm, max_price_sqm] range.
    # 0 means no limit on that bound.
    price_ok = (
        Deal.asking_price.isnot(None),
        Deal.size_sqm.isnot(None),
        Deal.size_sqm != 0,
        *(
            [Deal.asking_price / Deal.size_sqm <= max_price_sqm]
            if max_price_sqm > 0
            else []
        ),
        *(
            [Deal.asking_price / Deal.size_sqm >= min_price_sqm]
            if min_price_sqm > 0
            else []
        ),
    )

    # ------------------------------------------------------------------ #
    # 1. Totals
    # ------------------------------------------------------------------ #
    total_deals: int = db.query(func.count(Deal.id)).filter(*price_ok).scalar() or 0

    deals_with_prediction: int = (
        db.query(func.count(Prediction.deal_id.distinct()))
        .join(Deal, Prediction.deal_id == Deal.id)
        .filter(*price_ok)
        .scalar() or 0
    )

    market_avg_price_sqm_raw = (
        db.query(func.avg(Deal.asking_price / Deal.size_sqm))
        .filter(*price_ok)
        .scalar()
    )
    market_avg_price_sqm: Optional[float] = (
        float(market_avg_price_sqm_raw) if market_avg_price_sqm_raw is not None else None
    )

    # ------------------------------------------------------------------ #
    # 2. by_district — single grouped query + Python-side derived metrics
    # ------------------------------------------------------------------ #

    # Base district aggregates
    district_rows = (
        db.query(
            Deal.district,
            func.count(Deal.id).label("count"),
            func.avg(Deal.asking_price / Deal.size_sqm).label("avg_price_sqm"),
            func.avg(Deal.size_sqm).label("avg_size_sqm"),
            func.sum(case((Deal.condition == "renew", 1), else_=0)).label("n_renew"),
            func.sum(case((Deal.condition == "good", 1), else_=0)).label("n_good"),
            func.sum(case((Deal.condition == "newdevelopment", 1), else_=0)).label("n_new"),
            func.avg(
                case(
                    (
                        (Deal.condition == "renew") & Deal.asking_price.isnot(None) & Deal.size_sqm.isnot(None) & (Deal.size_sqm != 0),
                        Deal.asking_price / Deal.size_sqm,
                    ),
                    else_=None,
                )
            ).label("avg_price_renew"),
            func.avg(
                case(
                    (
                        (Deal.condition == "good") & Deal.asking_price.isnot(None) & Deal.size_sqm.isnot(None) & (Deal.size_sqm != 0),
                        Deal.asking_price / Deal.size_sqm,
                    ),
                    else_=None,
                )
            ).label("avg_price_good"),
        )
        .filter(Deal.district.isnot(None), *price_ok)
        .group_by(Deal.district)
        .all()
    )

    # ml_vs_ask_avg per district: join predictions → group by district
    ml_rows = (
        db.query(
            Deal.district,
            func.avg(
                (Prediction.predicted_price - Deal.asking_price) / Deal.asking_price
            ).label("ml_vs_ask_avg"),
        )
        .join(Prediction, Prediction.deal_id == Deal.id)
        .filter(
            Deal.district.isnot(None),
            Deal.asking_price != 0,
            *price_ok,
        )
        .group_by(Deal.district)
        .all()
    )
    ml_by_district: dict = {r.district: r.ml_vs_ask_avg for r in ml_rows}

    by_district = []
    for r in district_rows:
        count = r.count or 0
        pct_renew = float(r.n_renew) / count if count else 0.0
        pct_good = float(r.n_good) / count if count else 0.0
        pct_new = float(r.n_new) / count if count else 0.0

        avg_price_renew = float(r.avg_price_renew) if r.avg_price_renew is not None else None
        avg_price_good = float(r.avg_price_good) if r.avg_price_good is not None else None

        reform_upside: Optional[float] = (
            avg_price_good - avg_price_renew
            if avg_price_good is not None and avg_price_renew is not None
            else None
        )

        raw_ml = ml_by_district.get(r.district)
        ml_vs_ask_avg: Optional[float] = float(raw_ml) if raw_ml is not None else None

        by_district.append(
            {
                "district": r.district,
                "count": count,
                "avg_price_sqm": float(r.avg_price_sqm) if r.avg_price_sqm is not None else None,
                "avg_size_sqm": float(r.avg_size_sqm) if r.avg_size_sqm is not None else None,
                "pct_renew": pct_renew,
                "pct_good": pct_good,
                "pct_new": pct_new,
                "avg_price_renew": avg_price_renew,
                "avg_price_good": avg_price_good,
                "reform_upside": reform_upside,
                "ml_vs_ask_avg": ml_vs_ask_avg,
            }
        )

    # ------------------------------------------------------------------ #
    # 3. condition_by_district — for stacked bar chart
    # ------------------------------------------------------------------ #
    condition_by_district = [
        {
            "district": r.district,
            "renew": int(r.n_renew),
            "good": int(r.n_good),
            "new": int(r.n_new),
        }
        for r in district_rows
    ]

    # ------------------------------------------------------------------ #
    # 4. price_histogram
    # ------------------------------------------------------------------ #
    price_buckets_def = [
        ("<150k",      lambda p: p < 150_000),
        ("150–250k",   lambda p: 150_000 <= p < 250_000),
        ("250–350k",   lambda p: 250_000 <= p < 350_000),
        ("350–500k",   lambda p: 350_000 <= p < 500_000),
        ("500k–750k",  lambda p: 500_000 <= p < 750_000),
        ("750k–1M",    lambda p: 750_000 <= p < 1_000_000),
        (">1M",        lambda p: p >= 1_000_000),
    ]

    price_values = [
        r[0]
        for r in db.query(Deal.asking_price).filter(*price_ok).all()
    ]
    price_counts: dict = defaultdict(int)
    for p in price_values:
        for label, predicate in price_buckets_def:
            if predicate(p):
                price_counts[label] += 1
                break

    price_histogram = [
        {"bucket": label, "count": price_counts.get(label, 0)}
        for label, _ in price_buckets_def
    ]

    # ------------------------------------------------------------------ #
    # 5. size_histogram
    # ------------------------------------------------------------------ #
    size_buckets_def = [
        ("<50",    lambda s: s < 50),
        ("50–75",  lambda s: 50 <= s < 75),
        ("75–100", lambda s: 75 <= s < 100),
        ("100–150",lambda s: 100 <= s < 150),
        (">150",   lambda s: s >= 150),
    ]

    size_values = [
        r[0]
        for r in db.query(Deal.size_sqm).filter(*price_ok).all()
    ]
    size_counts: dict = defaultdict(int)
    for s in size_values:
        for label, predicate in size_buckets_def:
            if predicate(s):
                size_counts[label] += 1
                break

    size_histogram = [
        {"bucket": label, "count": size_counts.get(label, 0)}
        for label, _ in size_buckets_def
    ]

    # ------------------------------------------------------------------ #
    # 6. bedrooms_distribution
    # ------------------------------------------------------------------ #
    bedroom_rows = (
        db.query(Deal.bedrooms, func.count(Deal.id).label("count"))
        .filter(Deal.bedrooms.isnot(None), *price_ok)
        .group_by(Deal.bedrooms)
        .order_by(Deal.bedrooms.asc())
        .all()
    )
    bedrooms_distribution = [
        {"bedrooms": int(r.bedrooms), "count": int(r.count)} for r in bedroom_rows
    ]

    # ------------------------------------------------------------------ #
    # 7. amenities — fraction of all deals with each amenity = True
    # ------------------------------------------------------------------ #
    amenity_row = db.query(
        func.count(Deal.id).label("total"),
        func.sum(case((Deal.elevator == True, 1), else_=0)).label("elevator"),
        func.sum(case((Deal.terrace == True, 1), else_=0)).label("terrace"),
        func.sum(case((Deal.balcony == True, 1), else_=0)).label("balcony"),
        func.sum(case((Deal.garage == True, 1), else_=0)).label("garage"),
        func.sum(case((Deal.storage_room == True, 1), else_=0)).label("storage_room"),
    ).filter(*price_ok).one()

    _total = amenity_row.total or 1  # guard against zero-division
    amenities = {
        "elevator":    float(amenity_row.elevator or 0) / _total,
        "terrace":     float(amenity_row.terrace or 0) / _total,
        "balcony":     float(amenity_row.balcony or 0) / _total,
        "garage":      float(amenity_row.garage or 0) / _total,
        "storage_room": float(amenity_row.storage_room or 0) / _total,
    }

    # ------------------------------------------------------------------ #
    # 8. listed_over_time — group by year-month of created_at (PostgreSQL)
    # ------------------------------------------------------------------ #
    month_rows = (
        db.query(
            func.to_char(Deal.created_at, "YYYY-MM").label("month"),
            func.count(Deal.id).label("count"),
        )
        .filter(Deal.created_at.isnot(None))
        .group_by(func.to_char(Deal.created_at, "YYYY-MM"))
        .order_by(func.to_char(Deal.created_at, "YYYY-MM").asc())
        .all()
    )
    listed_over_time = [
        {"month": r.month, "count": int(r.count)} for r in month_rows
    ]

    # ------------------------------------------------------------------ #
    # 9. portfolio_summary — from financial_analyses
    # ------------------------------------------------------------------ #
    portfolio_row = db.query(
        func.count(FinancialAnalysis.id).label("total_analyses"),
        func.avg(FinancialAnalysis.irr).label("avg_irr"),
        func.avg(FinancialAnalysis.moic).label("avg_moic"),
        func.avg(FinancialAnalysis.return_on_equity).label("avg_roe"),
    ).one()

    portfolio_summary = {
        "total_analyses": int(portfolio_row.total_analyses or 0),
        "avg_irr":  float(portfolio_row.avg_irr)  if portfolio_row.avg_irr  is not None else None,
        "avg_moic": float(portfolio_row.avg_moic) if portfolio_row.avg_moic is not None else None,
        "avg_roe":  float(portfolio_row.avg_roe)  if portfolio_row.avg_roe  is not None else None,
    }

    # ------------------------------------------------------------------ #
    # Return
    # ------------------------------------------------------------------ #
    return {
        "total_deals": total_deals,
        "deals_with_prediction": deals_with_prediction,
        "market_avg_price_sqm": market_avg_price_sqm,
        "by_district": by_district,
        "condition_by_district": condition_by_district,
        "price_histogram": price_histogram,
        "size_histogram": size_histogram,
        "bedrooms_distribution": bedrooms_distribution,
        "amenities": amenities,
        "listed_over_time": listed_over_time,
        "portfolio_summary": portfolio_summary,
    }
