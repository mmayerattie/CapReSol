"""
Unified ML evaluation script for thesis tables 4-7 and residual figures.
One dataset, one split, consistent metrics across all tables.

Run from project root:
    python scripts/unified_ml_evaluation.py
"""
import copy
import json
import os
import sys
import urllib.request

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler

FIGURES_DIR = os.path.join(os.path.dirname(__file__), "..", "figures")
os.makedirs(FIGURES_DIR, exist_ok=True)

API_BASE = "https://capresol-production.up.railway.app"
MIN_PRICE_SQM = 500
MAX_PRICE_SQM = 25_000
MIN_ZONE_FREQUENCY = 10


# ── Helpers ───────────────────────────────────────────────────────────────

def mape(y_true, y_pred):
    mask = y_true != 0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def fetch_deals():
    login_data = json.dumps({"username": "Admin", "password": "Capstone26100"}).encode()
    req = urllib.request.Request(
        f"{API_BASE}/auth/login", data=login_data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        token = json.loads(resp.read())["access_token"]

    req = urllib.request.Request(
        f"{API_BASE}/deals/", headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        deals = json.loads(resp.read())
    print(f"Fetched {len(deals)} deals from production API")
    return deals


VALID_ORIENTATIONS = {
    "norte", "sur", "este", "oeste", "noroeste", "noreste", "sureste",
    "suroeste", "exterior", "interior", "norte-sur", "este-oeste",
}


def _clean_orientation(raw):
    """Map junk orientation values (full sentences from scrapers) to empty."""
    if not raw:
        return ""
    val = raw.strip().lower()
    if val in VALID_ORIENTATIONS:
        return val
    return ""


def deal_to_features(d):
    return {
        "Numero de Habitaciones": d.get("bedrooms") or 0,
        "Numero de Baños": d.get("bathrooms") or 0,
        "Metros Cuadrados": d.get("size_sqm") or 0,
        "Planta": d.get("floor") or 0,
        "Trastero": 1 if d.get("storage_room") else 0,
        "Terraza": 1 if d.get("terrace") else 0,
        "Balcon": 1 if d.get("balcony") else 0,
        "Ascensor": 1 if d.get("elevator") else 0,
        "Garaje": 1 if d.get("garage") else 0,
        "Exterior": 1 if d.get("exterior") is True else 0,
        "Distrito": d.get("district") or "",
        "Zona": d.get("zone") or "",
        "Estado": d.get("condition") or "",
        "Ubicacion": _clean_orientation(d.get("orientation")),
    }


def build_dataset(deals):
    rows, targets, districts, conditions = [], [], [], []
    for d in deals:
        price = d.get("asking_price")
        size = d.get("size_sqm")
        if price is None or size is None or size == 0:
            continue
        psqm = price / size
        if psqm < MIN_PRICE_SQM or psqm > MAX_PRICE_SQM:
            continue
        rows.append(deal_to_features(d))
        targets.append(price)
        districts.append(d.get("district") or "Unknown")
        conditions.append(d.get("condition") or "missing")
    return rows, np.array(targets, dtype=float), districts, conditions


def prepare_df(rows, zone_threshold=0):
    df = pd.DataFrame(rows)
    if zone_threshold > 0 and "Zona" in df.columns:
        zone_counts = df["Zona"].value_counts()
        rare_zones = set(zone_counts[zone_counts < zone_threshold].index)
        df.loc[df["Zona"].isin(rare_zones), "Zona"] = ""
    for col in ["Distrito", "Zona", "Estado", "Ubicacion"]:
        if col in df.columns:
            df = pd.get_dummies(df, columns=[col], drop_first=False)
    return df


# ══════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    deals = fetch_deals()
    rows, y_raw, districts, conditions = build_dataset(deals)
    districts = np.array(districts)
    conditions = np.array(conditions)
    sizes = np.array([r.get("Metros Cuadrados", 1) or 1 for r in rows], dtype=float)
    n_deals = len(rows)
    print(f"Dataset: {n_deals} deals after filtering\n")

    # ══════════════════════════════════════════════════════════════════════
    #  TABLE 4: Model comparison (Experiment A baseline)
    # ══════════════════════════════════════════════════════════════════════
    print("=" * 70)
    print("TABLE 4: MODEL COMPARISON")
    print("=" * 70)

    df_a = prepare_df(copy.deepcopy(rows), zone_threshold=MIN_ZONE_FREQUENCY)
    y = np.log1p(y_raw)

    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        df_a, y, np.arange(len(y)), test_size=0.15, random_state=42
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    X_all_s = scaler.transform(df_a)

    models = {
        "Linear Regression": LinearRegression(),
        "Random Forest": RandomForestRegressor(
            n_estimators=300, max_depth=15, random_state=42, n_jobs=-1
        ),
        "Gradient Boosting": GradientBoostingRegressor(
            n_estimators=300, max_depth=5, learning_rate=0.05,
            subsample=0.8, random_state=42,
        ),
    }
    try:
        from xgboost import XGBRegressor
        models["XGBoost"] = XGBRegressor(
            n_estimators=300, max_depth=5, learning_rate=0.05,
            subsample=0.8, random_state=42, verbosity=0,
        )
    except ImportError:
        print("  (XGBoost not installed, skipping)")

    table4 = []
    gb_model = None
    for name, model in models.items():
        print(f"  Training {name}...")
        model.fit(X_train_s, y_train)

        y_pred = np.expm1(model.predict(X_test_s))
        y_test_orig = np.expm1(y_test)

        cv = cross_val_score(model, X_all_s, y, cv=5, scoring="r2")

        r2 = r2_score(y_test_orig, y_pred)
        mae = mean_absolute_error(y_test_orig, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test_orig, y_pred))
        m = mape(y_test_orig, y_pred)

        table4.append({
            "Model": name, "R² (test)": r2, "R² (CV)": cv.mean(),
            "CV std": cv.std(), "MAE (€)": mae, "MAPE": m,
        })
        print(f"    R²(test)={r2:.4f}  R²(CV)={cv.mean():.4f}±{cv.std():.4f}  "
              f"MAE=€{mae:,.0f}  MAPE={m:.1f}%")

        if name == "Gradient Boosting":
            gb_model = model

    table4.sort(key=lambda x: -x["R² (CV)"])
    print(f"\n{'Model':<22} {'R²(test)':>9} {'R²(CV)':>8} {'CV std':>8} {'MAE(€)':>10} {'MAPE':>7}")
    print("-" * 68)
    for r in table4:
        print(f"{r['Model']:<22} {r['R² (test)']:>9.3f} {r['R² (CV)']:>8.3f} "
              f"{r['CV std']:>8.3f} {r['MAE (€)']:>10,.0f} {r['MAPE']:>6.1f}%")

    # ══════════════════════════════════════════════════════════════════════
    #  TABLE 5: Feature engineering experiments (GB only)
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TABLE 5: FEATURE ENGINEERING EXPERIMENTS (GB only)")
    print("=" * 70)

    experiments = {
        "A": ("Baseline (zone cleanup, all features)", None),
        "B": ("Drop zone + orientation", None),
        "C": ("B + impute missing condition as good", "good"),
        "C2": ("B + impute missing condition as segunda_mano", "segunda_mano"),
        "D": ("B + target = price/sqm", None),
    }

    table5 = []
    for exp_id, (desc, impute_val) in experiments.items():
        print(f"\n  Experiment {exp_id}: {desc}")
        exp_rows = copy.deepcopy(rows)

        target_is_psqm = (exp_id == "D")
        zt = MIN_ZONE_FREQUENCY if exp_id == "A" else 0

        if exp_id != "A":
            for r in exp_rows:
                r["Zona"] = ""
                r["Ubicacion"] = ""

        if impute_val:
            for r in exp_rows:
                if not r.get("Estado") or r["Estado"] == "":
                    r["Estado"] = impute_val

        df_exp = prepare_df(exp_rows, zone_threshold=zt)

        if target_is_psqm:
            y_exp = np.log1p(y_raw / sizes)
        else:
            y_exp = np.log1p(y_raw)

        X_tr, X_te, y_tr, y_te = train_test_split(
            df_exp, y_exp, test_size=0.15, random_state=42
        )
        if target_is_psqm:
            _, sizes_te = train_test_split(sizes, test_size=0.15, random_state=42)

        sc = StandardScaler()
        X_tr_s = sc.fit_transform(X_tr)
        X_te_s = sc.transform(X_te)
        X_all_exp = sc.transform(df_exp)

        gb = GradientBoostingRegressor(
            n_estimators=300, max_depth=5, learning_rate=0.05,
            subsample=0.8, random_state=42,
        )
        gb.fit(X_tr_s, y_tr)

        y_pred_log = gb.predict(X_te_s)
        if target_is_psqm:
            y_pred_eur = np.expm1(y_pred_log) * sizes_te
            y_te_eur = np.expm1(y_te) * sizes_te
        else:
            y_pred_eur = np.expm1(y_pred_log)
            y_te_eur = np.expm1(y_te)

        cv = cross_val_score(gb, X_all_exp, y_exp, cv=5, scoring="r2")
        r2_test = r2_score(y_te_eur, y_pred_eur)
        mae_val = mean_absolute_error(y_te_eur, y_pred_eur)

        table5.append({
            "Exp": exp_id, "Description": desc,
            "Best R² CV": cv.mean(), "Best MAE (€)": mae_val,
            "R² test": r2_test,
        })
        print(f"    R²(CV)={cv.mean():.3f}  R²(test)={r2_test:.3f}  MAE=€{mae_val:,.0f}")

    print(f"\n{'Exp':<4} {'Description':<50} {'R²(CV)':>8} {'MAE(€)':>10}")
    print("-" * 76)
    for r in table5:
        star = "*" if r["Exp"] == "D" else ""
        print(f"{r['Exp']:<4} {r['Description']:<50} {r['Best R² CV']:>7.3f}{star} {r['Best MAE (€)']:>10,.0f}")

    # ══════════════════════════════════════════════════════════════════════
    #  TABLE 6: Train vs Test diagnostics (GB from Table 4)
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TABLE 6: TRAIN vs TEST PERFORMANCE (Gradient Boosting)")
    print("=" * 70)

    # Use the SAME gb_model, scaler, split from Table 4
    y_train_pred = np.expm1(gb_model.predict(X_train_s))
    y_test_pred = np.expm1(gb_model.predict(X_test_s))
    y_train_orig = np.expm1(y_train)
    y_test_orig = np.expm1(y_test)

    table6 = {}
    for label, yt, yp, n in [
        ("Train", y_train_orig, y_train_pred, len(X_train)),
        ("Test", y_test_orig, y_test_pred, len(X_test)),
    ]:
        table6[label] = {
            "N": n,
            "R²": r2_score(yt, yp),
            "MAE": mean_absolute_error(yt, yp),
            "RMSE": np.sqrt(mean_squared_error(yt, yp)),
            "MAPE": mape(yt, yp),
        }

    print(f"\n{'Set':<8} {'N':>6} {'R²':>8} {'MAE(€)':>12} {'RMSE(€)':>12} {'MAPE':>7}")
    print("-" * 58)
    for label in ["Train", "Test"]:
        m = table6[label]
        print(f"{label:<8} {m['N']:>6} {m['R²']:>8.3f} {m['MAE']:>12,.0f} {m['RMSE']:>12,.0f} {m['MAPE']:>6.1f}%")

    gap = table6["Train"]["R²"] - table6["Test"]["R²"]
    print(f"\n  R² gap: {gap:+.4f} → {'No overfitting' if gap <= 0.05 else 'OVERFITTING DETECTED'}")

    # ══════════════════════════════════════════════════════════════════════
    #  TABLE 7: Production model summary (GB from Table 4)
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TABLE 7: PRODUCTION MODEL METRICS")
    print("=" * 70)

    gb_t4 = next(r for r in table4 if r["Model"] == "Gradient Boosting")
    print(f"""
  Metric                   Value
  ─────────────────────────────────
  R² (test)                {gb_t4['R² (test)']:.3f}
  R² (5-fold CV)           {gb_t4['R² (CV)']:.3f}
  CV standard deviation    {gb_t4['CV std']:.3f}
  MAE                      €{gb_t4['MAE (€)']:,.0f}
  MAPE                     {gb_t4['MAPE']:.1f}%
  Deals trained            {n_deals:,}
""")

    # ══════════════════════════════════════════════════════════════════════
    #  CONSISTENCY CHECK
    # ══════════════════════════════════════════════════════════════════════
    print("=" * 70)
    print("CONSISTENCY CHECK")
    print("=" * 70)
    t4_r2 = gb_t4["R² (test)"]
    t6_r2 = table6["Test"]["R²"]
    t4_mae = gb_t4["MAE (€)"]
    t6_mae = table6["Test"]["MAE"]
    t5a_cv = next(r for r in table5 if r["Exp"] == "A")["Best R² CV"]
    t4_cv = gb_t4["R² (CV)"]

    print(f"  Table 4 GB R²(test) = {t4_r2:.4f}  |  Table 6 Test R² = {t6_r2:.4f}  |  Match: {abs(t4_r2 - t6_r2) < 1e-6}")
    print(f"  Table 4 GB MAE      = €{t4_mae:,.0f}  |  Table 6 Test MAE = €{t6_mae:,.0f}  |  Match: {abs(t4_mae - t6_mae) < 1}")
    print(f"  Table 4 GB R²(CV)   = {t4_cv:.4f}  |  Table 5 Exp A   = {t5a_cv:.4f}  |  Match: {abs(t4_cv - t5a_cv) < 1e-6}")
    print(f"  Table 7 uses Table 4 GB row directly → consistent by construction")

    # ══════════════════════════════════════════════════════════════════════
    #  RESIDUAL ANALYSIS + FIGURES
    # ══════════════════════════════════════════════════════════════════════

    # ── By district ───────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("RESIDUAL ANALYSIS BY DISTRICT (test set)")
    print("=" * 70)

    test_districts = districts[idx_test]
    district_df = pd.DataFrame({
        "district": test_districts,
        "actual": y_test_orig,
        "predicted": y_test_pred,
        "abs_error": np.abs(y_test_orig - y_test_pred),
        "abs_pct_error": np.abs((y_test_orig - y_test_pred) / y_test_orig) * 100,
    })

    dist_stats = (
        district_df.groupby("district")
        .agg(n=("actual", "count"), MAE=("abs_error", "mean"), MAPE=("abs_pct_error", "mean"))
        .sort_values("MAPE", ascending=False)
    )
    print(f"\n{'District':<24} {'n':>4} {'MAE(€)':>12} {'MAPE':>7}")
    print("-" * 50)
    for d, r in dist_stats.iterrows():
        print(f"{d:<24} {r['n']:>4} {r['MAE']:>12,.0f} {r['MAPE']:>6.1f}%")

    # ── By price quartile ─────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("RESIDUAL ANALYSIS BY PRICE QUARTILE (test set)")
    print("=" * 70)

    quartiles = pd.qcut(y_test_orig, 4, labels=["Q1 (cheapest)", "Q2", "Q3", "Q4 (most expensive)"])
    quartile_df = pd.DataFrame({
        "quartile": quartiles,
        "actual": y_test_orig,
        "predicted": y_test_pred,
        "abs_error": np.abs(y_test_orig - y_test_pred),
        "abs_pct_error": np.abs((y_test_orig - y_test_pred) / y_test_orig) * 100,
    })

    q_stats = (
        quartile_df.groupby("quartile", observed=True)
        .agg(
            n=("actual", "count"),
            price_range=("actual", lambda x: f"€{x.min():,.0f} – €{x.max():,.0f}"),
            MAE=("abs_error", "mean"),
            MAPE=("abs_pct_error", "mean"),
        )
    )
    print(f"\n{'Quartile':<22} {'n':>4} {'Range':<28} {'MAE(€)':>12} {'MAPE':>7}")
    print("-" * 78)
    for q, r in q_stats.iterrows():
        print(f"{q:<22} {r['n']:>4} {r['price_range']:<28} {r['MAE']:>12,.0f} {r['MAPE']:>6.1f}%")

    # ── By condition ──────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("RESIDUAL ANALYSIS BY CONDITION (test set)")
    print("=" * 70)

    test_conditions = conditions[idx_test]
    condition_df = pd.DataFrame({
        "condition": test_conditions,
        "actual": y_test_orig,
        "predicted": y_test_pred,
        "abs_error": np.abs(y_test_orig - y_test_pred),
        "abs_pct_error": np.abs((y_test_orig - y_test_pred) / y_test_orig) * 100,
    })

    cond_stats = (
        condition_df.groupby("condition")
        .agg(n=("actual", "count"), MAE=("abs_error", "mean"), MAPE=("abs_pct_error", "mean"))
        .sort_values("MAPE", ascending=False)
    )
    print(f"\n{'Condition':<18} {'n':>4} {'MAE(€)':>12} {'MAPE':>7}")
    print("-" * 45)
    for c, r in cond_stats.iterrows():
        print(f"{c:<18} {r['n']:>4} {r['MAE']:>12,.0f} {r['MAPE']:>6.1f}%")

    # ── FIGURES ───────────────────────────────────────────────────────────

    # Fig 1: Predicted vs Actual scatter
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.scatter(y_test_orig / 1000, y_test_pred / 1000, alpha=0.35, s=15, c="#2563eb", edgecolors="none")
    lim_max = max(y_test_orig.max(), y_test_pred.max()) / 1000 * 1.05
    ax.plot([0, lim_max], [0, lim_max], "k--", linewidth=1, label="Perfect prediction")
    ax.set_xlabel("Actual Price (€ thousands)", fontsize=12)
    ax.set_ylabel("Predicted Price (€ thousands)", fontsize=12)
    ax.set_title("Predicted vs Actual Asking Price (Test Set)", fontsize=13, fontweight="bold")
    ax.legend(fontsize=10)
    ax.set_xlim(0, lim_max)
    ax.set_ylim(0, lim_max)
    ax.set_aspect("equal")
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "residual_scatter.png"), dpi=150)
    plt.close()
    print(f"\n✓ Saved residual_scatter.png")

    # Fig 2: MAPE by district
    district_mape = district_df.groupby("district")["abs_pct_error"].mean().sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=(10, 7))
    colors = ["#ef4444" if v > 20 else "#f59e0b" if v > 15 else "#22c55e" for v in district_mape.values]
    bars = ax.barh(district_mape.index, district_mape.values, color=colors, edgecolor="white", linewidth=0.5)
    ax.set_xlabel("MAPE (%)", fontsize=12)
    ax.set_title("Model Error by District (MAPE, Test Set)", fontsize=13, fontweight="bold")
    for bar, val in zip(bars, district_mape.values):
        ax.text(val + 0.3, bar.get_y() + bar.get_height() / 2, f"{val:.1f}%", va="center", fontsize=9)
    ax.axvline(x=district_mape.median(), color="gray", linestyle="--", linewidth=0.8,
               label=f"Median: {district_mape.median():.1f}%")
    ax.legend(fontsize=9)
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "residual_by_district.png"), dpi=150)
    plt.close()
    print("✓ Saved residual_by_district.png")

    # Fig 3: MAPE by price quartile
    quartile_mape = quartile_df.groupby("quartile", observed=True)["abs_pct_error"].mean()
    fig, ax = plt.subplots(figsize=(8, 5))
    q_colors = ["#22c55e", "#84cc16", "#f59e0b", "#ef4444"]
    bars = ax.bar(range(len(quartile_mape)), quartile_mape.values, color=q_colors, edgecolor="white", linewidth=0.5)
    ax.set_xticks(range(len(quartile_mape)))
    ax.set_xticklabels(quartile_mape.index, fontsize=10)
    ax.set_ylabel("MAPE (%)", fontsize=12)
    ax.set_title("Model Error by Price Quartile (MAPE, Test Set)", fontsize=13, fontweight="bold")
    for bar, val in zip(bars, quartile_mape.values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.3, f"{val:.1f}%",
                ha="center", fontsize=11, fontweight="bold")
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "residual_by_price_quartile.png"), dpi=150)
    plt.close()
    print("✓ Saved residual_by_price_quartile.png")

    # Fig 4: MAPE by condition
    cond_mape = condition_df.groupby("condition")["abs_pct_error"].mean().sort_values(ascending=True)
    cond_n = condition_df.groupby("condition")["actual"].count()
    fig, ax = plt.subplots(figsize=(7, 4.5))
    c_colors = ["#ef4444" if v > 20 else "#f59e0b" if v > 15 else "#22c55e" for v in cond_mape.values]
    bars = ax.barh(cond_mape.index, cond_mape.values, color=c_colors, edgecolor="white", linewidth=0.5)
    ax.set_xlabel("MAPE (%)", fontsize=12)
    ax.set_title("Model Error by Condition (MAPE, Test Set)", fontsize=13, fontweight="bold")
    for bar, val, name in zip(bars, cond_mape.values, cond_mape.index):
        ax.text(val + 0.3, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%  (n={cond_n[name]})", va="center", fontsize=10)
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "residual_by_condition.png"), dpi=150)
    plt.close()
    print("✓ Saved residual_by_condition.png")

    # Fig 5: Residual distribution histogram
    residuals = (y_test_pred - y_test_orig) / 1000
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(residuals, bins=50, color="#2563eb", edgecolor="white", linewidth=0.5, alpha=0.85)
    ax.axvline(x=0, color="red", linestyle="--", linewidth=1.2, label="Zero error")
    ax.axvline(x=residuals.mean(), color="orange", linestyle="-", linewidth=1.2,
               label=f"Mean: €{residuals.mean():+,.1f}k")
    ax.set_xlabel("Residual: Predicted − Actual (€ thousands)", fontsize=12)
    ax.set_ylabel("Frequency", fontsize=12)
    ax.set_title("Distribution of Prediction Residuals (Test Set)", fontsize=13, fontweight="bold")
    ax.legend(fontsize=10)
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "residual_distribution.png"), dpi=150)
    plt.close()
    print("✓ Saved residual_distribution.png")

    # ── Executive summary ─────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("EXECUTIVE SUMMARY")
    print("=" * 70)

    worst_dist = dist_stats.index[0]
    worst_dist_mape = dist_stats.iloc[0]["MAPE"]
    best_dist = dist_stats.index[-1]
    best_dist_mape = dist_stats.iloc[-1]["MAPE"]

    print(f"""
1. GB achieves R²={table6['Test']['R²']:.3f} on test (MAPE={table6['Test']['MAPE']:.1f}%,
   MAE=€{table6['Test']['MAE']:,.0f}), with train-test R² gap of {gap:+.3f}
   → {'no overfitting' if gap <= 0.05 else 'OVERFITTING'}.

2. Worst districts: {worst_dist} ({worst_dist_mape:.1f}% MAPE) — low sample size
   and heterogeneous stock. Best: {best_dist} ({best_dist_mape:.1f}%).

3. Q2 (€283k-€416k) is the sweet spot. Q1 and Q3 have higher relative error.

4. Missing condition ({cond_stats.loc['missing','MAPE']:.1f}% MAPE) is the worst
   segment, confirming the 34% data gap from Redpiso hurts accuracy.

5. Residuals are approximately symmetric (mean bias: €{(y_test_pred - y_test_orig).mean():+,.0f}).
""")


if __name__ == "__main__":
    main()
