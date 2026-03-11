"""
Fix & Flip financial model — pure Python implementation.
Formula reference: ModelEconomics.xlsx (Claudio Coello 73 example)

Cash flow convention: negative = outflow, positive = inflow.
All cash flows are from the EQUITY investor perspective (debt is netted out).
IRR is computed on monthly equity cash flows using numpy_financial.
"""
import numpy_financial as npf


def run_flip_analysis(
    size_sqm: float,
    purchase_price: float,
    capex_total: float,
    capex_months: int,
    project_months: int,
    exit_price_per_sqm: float,
    monthly_opex: float,            # utilities + community fees
    ibi_annual: float,
    closing_costs_pct: float,       # ITP + notario + AJD + lawyers (decimal, e.g. 0.075)
    broker_fee_pct: float,          # exit broker fee incl. VAT (e.g. 0.0363)
    mortgage_ltv: float = 0.0,      # % of purchase financed (e.g. 0.60)
    mortgage_rate_annual: float = 0.0,  # annual interest rate on mortgage (e.g. 0.067)
    capex_debt: float = 0.0,        # portion of capex financed by debt
    capex_debt_rate_annual: float = 0.0,
    tax_rate: float = 0.0,
) -> dict:
    """
    Returns a dict with IRR, MOIC, ROE, gross_margin, profit, and summary totals.
    Cash flows are equity-only: debt is drawn at closing and repaid at exit.
    """
    # ── Debt sizing ────────────────────────────────────────────────────────
    mortgage_debt = purchase_price * mortgage_ltv
    equity_at_purchase = purchase_price - mortgage_debt

    closing_costs = purchase_price * closing_costs_pct

    capex_equity = capex_total - capex_debt
    capex_equity_monthly = capex_equity / capex_months if capex_months > 0 else 0

    # Monthly interest (interest-only during hold period)
    mortgage_interest_monthly = mortgage_debt * (mortgage_rate_annual / 12)
    capex_interest_monthly = capex_debt * (capex_debt_rate_annual / 12)
    total_interest_monthly = mortgage_interest_monthly + capex_interest_monthly

    # ── Exit ───────────────────────────────────────────────────────────────
    gross_exit_price = exit_price_per_sqm * size_sqm
    broker_fee = gross_exit_price * broker_fee_pct
    net_exit_price = gross_exit_price - broker_fee
    debt_repayment = mortgage_debt + capex_debt

    # ── Monthly equity cash flows ──────────────────────────────────────────
    # Month 0: equity portion of purchase + closing costs
    cash_flows = [-(equity_at_purchase + closing_costs)]

    for month in range(1, project_months + 1):
        cf = 0.0
        # Equity capex during renovation period
        if month <= capex_months:
            cf -= capex_equity_monthly
        # Running opex + IBI every month
        cf -= monthly_opex
        cf -= ibi_annual / 12
        # Interest on debt every month (while debt is outstanding)
        cf -= total_interest_monthly
        # Exit: net proceeds minus debt repayment
        if month == project_months:
            cf += net_exit_price - debt_repayment
        cash_flows.append(cf)

    # ── Totals ─────────────────────────────────────────────────────────────
    total_opex = monthly_opex * project_months
    total_ibi = ibi_annual * (project_months / 12)
    total_interest = total_interest_monthly * project_months
    total_dev_cost = (purchase_price + closing_costs + capex_total
                      + total_opex + total_ibi + total_interest)

    profit_pre_tax = net_exit_price - total_dev_cost
    tax = max(0.0, profit_pre_tax * tax_rate)
    profit = profit_pre_tax - tax

    # ── Max equity exposure (peak negative cumulative CF) ──────────────────
    running = 0.0
    max_equity = 0.0
    for cf in cash_flows:
        running += cf
        if running < max_equity:
            max_equity = running
    max_equity_abs = abs(max_equity)

    # ── Return metrics ─────────────────────────────────────────────────────
    moic = (max_equity_abs + profit) / max_equity_abs if max_equity_abs else 0.0
    roe = profit / max_equity_abs if max_equity_abs else 0.0
    gross_margin = profit / total_dev_cost if total_dev_cost else 0.0

    try:
        monthly_irr = npf.irr(cash_flows)
        irr = (1 + monthly_irr) ** 12 - 1 if monthly_irr is not None else None
    except Exception:
        irr = None

    return {
        "irr": round(irr, 6) if irr is not None else None,
        "moic": round(moic, 4),
        "return_on_equity": round(roe, 4),
        "gross_margin": round(gross_margin, 4),
        "profit": round(profit, 2),
        "gross_exit_price": round(gross_exit_price, 2),
        "net_exit_price": round(net_exit_price, 2),
        "total_dev_cost": round(total_dev_cost, 2),
        "max_equity_exposure": round(max_equity_abs, 2),
        "closing_costs": round(closing_costs, 2),
        "broker_fee": round(broker_fee, 2),
        "mortgage_debt": round(mortgage_debt, 2),
        "total_debt": round(mortgage_debt + capex_debt, 2),
    }
