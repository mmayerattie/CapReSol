from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Deal, Prediction, FinancialAnalysis, NotaryStat
from app.api.auth import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])

# Mapping notary filters → deal field values
_CONDITION_MAP = {
    "segunda_mano": ["renew", "good"],
    "nueva": ["newdevelopment"],
    "todos": None,
}
_PTYPE_PISOS = ["piso", "flat", "apartment", "ático", "estudio", "dúplex", "loft", "apartamento", "planta baja"]
_PTYPE_CASAS = ["casa", "chalet", "casa adosada", "casa o chalet"]
_PTYPE_MAP = {
    "pisos": _PTYPE_PISOS,
    "casas": _PTYPE_CASAS,
    "todos": None,
}


@router.get("")
def get_analytics(
    db: Session = Depends(get_db),
    max_price_sqm: int = 25000,
    min_price_sqm: int = 500,
    notary_construction: str = "segunda_mano",
    notary_class: str = "pisos",
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
            func.avg(
                case(
                    (
                        (Deal.condition == "renew") & Deal.size_sqm.isnot(None),
                        Deal.size_sqm,
                    ),
                    else_=None,
                )
            ).label("avg_size_renew"),
            func.avg(
                case(
                    (
                        (Deal.condition == "newdevelopment") & Deal.asking_price.isnot(None) & Deal.size_sqm.isnot(None) & (Deal.size_sqm != 0),
                        Deal.asking_price / Deal.size_sqm,
                    ),
                    else_=None,
                )
            ).label("avg_price_new"),
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
                "avg_price_new": float(r.avg_price_new) if r.avg_price_new is not None else None,
                "avg_size_renew": float(r.avg_size_renew) if r.avg_size_renew is not None else None,
                "n_renew": int(r.n_renew),
                "n_good": int(r.n_good),
                "n_new": int(r.n_new),
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
    # 8. listed_over_time — group by year-month of listed_date (not created_at)
    # ------------------------------------------------------------------ #
    month_rows = (
        db.query(
            func.to_char(Deal.listed_date, "YYYY-MM").label("month"),
            func.count(Deal.id).label("count"),
        )
        .filter(Deal.listed_date.isnot(None), *price_ok)
        .group_by(func.to_char(Deal.listed_date, "YYYY-MM"))
        .order_by(func.to_char(Deal.listed_date, "YYYY-MM").asc())
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
    # 10. notary_spread — ask vs close price, unified filters on both sides
    # ------------------------------------------------------------------ #

    # Build postal_code → district mapping from deals
    postal_district_rows = (
        db.query(Deal.postal_code, Deal.district)
        .filter(Deal.postal_code.isnot(None), Deal.district.isnot(None))
        .distinct()
        .all()
    )
    postal_to_district: dict = {}
    for row in postal_district_rows:
        if row.postal_code not in postal_to_district:
            postal_to_district[row.postal_code] = row.district

    # Helper: aggregate notary rows by district (weighted by transaction count)
    def _agg_notary(construction_type: str, property_class: str) -> dict:
        rows = (
            db.query(NotaryStat)
            .filter(
                NotaryStat.construction_type == construction_type,
                NotaryStat.property_class == property_class,
            )
            .all()
        )
        agg: dict = {}
        for ns in rows:
            district = postal_to_district.get(ns.postal_code)
            if not district or not ns.notary_price_sqm:
                continue
            if district not in agg:
                agg[district] = {"sum": 0, "count": 0, "transactions": 0}
            a = agg[district]
            a["sum"] += ns.notary_price_sqm * (ns.notary_transactions or 1)
            a["count"] += ns.notary_transactions or 1
            a["transactions"] += ns.notary_transactions or 0
        return {d: {"psqm": round(v["sum"] / v["count"]), "transactions": v["transactions"]}
                for d, v in agg.items() if v["count"] > 0}

    # Main notary aggregation for the selected filters
    district_notary = _agg_notary(notary_construction, notary_class)

    # Filtered asking price per district (unified with notary filter dimensions)
    deal_conditions = _CONDITION_MAP.get(notary_construction)
    deal_types = _PTYPE_MAP.get(notary_class)

    filtered_ask_q = (
        db.query(
            Deal.district,
            func.avg(Deal.asking_price / Deal.size_sqm).label("avg_psqm"),
            func.count(Deal.id).label("cnt"),
        )
        .filter(Deal.district.isnot(None), *price_ok)
    )
    if deal_conditions:
        filtered_ask_q = filtered_ask_q.filter(Deal.condition.in_(deal_conditions))
    if deal_types:
        filtered_ask_q = filtered_ask_q.filter(func.lower(Deal.property_type).in_(deal_types))
    filtered_ask_rows = filtered_ask_q.group_by(Deal.district).all()
    filtered_ask = {r.district: {"psqm": float(r.avg_psqm), "count": int(r.cnt)}
                    for r in filtered_ask_rows if r.avg_psqm}

    notary_by_district = []
    for d in by_district:
        dn = district_notary.get(d["district"])
        fa = filtered_ask.get(d["district"])
        if dn and fa:
            spread_pct = (fa["psqm"] - dn["psqm"]) / dn["psqm"] * 100
            notary_by_district.append({
                "district": d["district"],
                "avg_asking_psqm": round(fa["psqm"]),
                "avg_notary_psqm": dn["psqm"],
                "spread_pct": round(spread_pct, 1),
                "notary_transactions": dn["transactions"],
                "asking_count": fa["count"],
            })
    notary_by_district.sort(key=lambda x: x["spread_pct"])

    # Notary prices by construction type (for flexible upside comparison)
    notary_prices_by_type = {
        "segunda_mano": {d: v["psqm"] for d, v in _agg_notary("segunda_mano", notary_class).items()},
        "nueva": {d: v["psqm"] for d, v in _agg_notary("nueva", notary_class).items()},
    }

    # ------------------------------------------------------------------ #
    # 11. opportunity_score — composite rank per district
    # ------------------------------------------------------------------ #
    # Score = weighted rank across: low €/m² (entry price), high reform upside,
    # positive ML spread. Each metric ranked 1..N (best=1), then averaged.
    scored = []
    for d in by_district:
        scored.append({**d, "_score_raw": []})

    # Rank by avg_price_sqm ascending (cheapest = best)
    by_price_asc = sorted(
        [d for d in scored if d.get("avg_price_sqm") is not None],
        key=lambda d: d["avg_price_sqm"],
    )
    for rank, d in enumerate(by_price_asc, 1):
        d["_score_raw"].append(rank)

    # Rank by reform_upside descending (biggest gap = best)
    by_upside = sorted(
        [d for d in scored if d.get("reform_upside") is not None and d["reform_upside"] > 0],
        key=lambda d: d["reform_upside"],
        reverse=True,
    )
    for rank, d in enumerate(by_upside, 1):
        d["_score_raw"].append(rank)

    # Rank by ml_vs_ask_avg descending (most undervalued = best)
    by_ml = sorted(
        [d for d in scored if d.get("ml_vs_ask_avg") is not None],
        key=lambda d: d["ml_vs_ask_avg"],
        reverse=True,
    )
    for rank, d in enumerate(by_ml, 1):
        d["_score_raw"].append(rank)

    # Compute avg rank → lower is better → convert to 1-10 score
    for d in scored:
        ranks = d.pop("_score_raw")
        d["opportunity_score"] = round(sum(ranks) / len(ranks), 1) if ranks else None

    # Sort by opportunity_score ascending (best first)
    opportunity_table = sorted(
        [d for d in scored if d.get("opportunity_score") is not None],
        key=lambda d: d["opportunity_score"],
    )

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
        "opportunity_table": opportunity_table,
        "notary_by_district": notary_by_district,
        "notary_prices_by_type": notary_prices_by_type,
    }
