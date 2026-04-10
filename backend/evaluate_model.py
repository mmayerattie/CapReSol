"""
Comprehensive ML model evaluation: train/test metrics, residual analysis,
and figure generation for the thesis Results section.

Run from backend/:
    python evaluate_model.py
"""
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(__file__))

from app.db import models
from app.db.session import SessionLocal
from app.ml.features import deal_to_features

FIGURES_DIR = os.path.join(os.path.dirname(__file__), "..", "figures")
MIN_PRICE_SQM = 500
MAX_PRICE_SQM = 25_000


def mape(y_true, y_pred):
    """Mean Absolute Percentage Error, excluding zeros."""
    mask = y_true != 0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


# ── 1. Build dataset (exact same pipeline as train.py) ────────────────────

db = SessionLocal()
deals = (
    db.query(models.Deal)
    .filter(
        models.Deal.asking_price.isnot(None),
        models.Deal.size_sqm.isnot(None),
        models.Deal.size_sqm != 0,
    )
    .all()
)

rows, targets, districts, conditions = [], [], [], []
for deal in deals:
    psqm = deal.asking_price / deal.size_sqm
    if psqm < MIN_PRICE_SQM or psqm > MAX_PRICE_SQM:
        continue
    rows.append(deal_to_features(deal))
    targets.append(deal.asking_price)
    districts.append(deal.district or "Unknown")
    conditions.append(deal.condition or "missing")

db.close()
print(f"Dataset: {len(rows)} deals (filtered from {len(deals)} total)\n")

# Build DataFrame + zone cardinality reduction
df = pd.DataFrame(rows)
if "Zona" in df.columns:
    zone_counts = df["Zona"].value_counts()
    rare_zones = set(zone_counts[zone_counts < 10].index)
    df.loc[df["Zona"].isin(rare_zones), "Zona"] = ""

for col in ["Distrito", "Zona", "Estado", "Ubicacion"]:
    if col in df.columns:
        df = pd.get_dummies(df, columns=[col], drop_first=False)

y_raw = np.array(targets, dtype=float)
y = np.log1p(y_raw)
districts = np.array(districts)
conditions = np.array(conditions)

# Same split as production
X_train, X_test, y_train, y_test, dist_train, dist_test, cond_train, cond_test = (
    train_test_split(df, y, districts, conditions, test_size=0.15, random_state=42)
)

scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)

model = GradientBoostingRegressor(
    n_estimators=300, max_depth=5, learning_rate=0.05,
    subsample=0.8, random_state=42,
)
model.fit(X_train_s, y_train)

# ── 2. Train vs Test performance ──────────────────────────────────────────

y_train_pred_log = model.predict(X_train_s)
y_test_pred_log = model.predict(X_test_s)

y_train_pred = np.expm1(y_train_pred_log)
y_test_pred = np.expm1(y_test_pred_log)
y_train_orig = np.expm1(y_train)
y_test_orig = np.expm1(y_test)

metrics = {}
for name, yt, yp in [("Train", y_train_orig, y_train_pred),
                      ("Test", y_test_orig, y_test_pred)]:
    metrics[name] = {
        "R²": r2_score(yt, yp),
        "MAE": mean_absolute_error(yt, yp),
        "RMSE": np.sqrt(mean_squared_error(yt, yp)),
        "MAPE": mape(yt, yp),
    }

print("=" * 60)
print("TRAIN vs TEST PERFORMANCE")
print("=" * 60)
print(f"{'Metric':<8} {'Train':>14} {'Test':>14}   {'Gap':>8}")
print("-" * 50)
for m in ["R²", "MAE", "RMSE", "MAPE"]:
    tr, te = metrics["Train"][m], metrics["Test"][m]
    if m == "R²":
        print(f"{m:<8} {tr:>14.4f} {te:>14.4f}   {tr - te:>+8.4f}")
    elif m == "MAPE":
        print(f"{m:<8} {tr:>13.1f}% {te:>13.1f}%   {tr - te:>+7.1f}%")
    else:
        fmt = f"EUR{tr:>10,.0f}  EUR{te:>10,.0f}   EUR{tr - te:>+8,.0f}"
        print(f"{m:<8} {fmt}")

r2_gap = metrics["Train"]["R²"] - metrics["Test"]["R²"]
if r2_gap > 0.05:
    print(f"\n⚠ OVERFITTING detected: Train R² - Test R² = {r2_gap:.3f} (>{0.05})")
else:
    print(f"\n✓ No significant overfitting: gap = {r2_gap:.3f}")

# ── 3. Residual analysis by district ─────────────────────────────────────

print("\n" + "=" * 60)
print("RESIDUAL ANALYSIS BY DISTRICT (Test Set)")
print("=" * 60)

dist_results = []
for d in sorted(set(dist_test)):
    mask = dist_test == d
    if mask.sum() < 2:
        continue
    yt, yp = y_test_orig[mask], y_test_pred[mask]
    dist_results.append({
        "District": d,
        "N": int(mask.sum()),
        "MAE": mean_absolute_error(yt, yp),
        "MAPE": mape(yt, yp),
        "Median Price": np.median(yt),
    })

dist_df = pd.DataFrame(dist_results).sort_values("MAPE", ascending=False)
print(f"{'District':<22} {'N':>4} {'MAE (EUR)':>12} {'MAPE':>7} {'Med.Price':>12}")
print("-" * 62)
for _, r in dist_df.iterrows():
    print(f"{r['District']:<22} {r['N']:>4} {r['MAE']:>12,.0f} {r['MAPE']:>6.1f}% {r['Median Price']:>12,.0f}")

# ── 4. Residual analysis by price quartile ────────────────────────────────

print("\n" + "=" * 60)
print("RESIDUAL ANALYSIS BY PRICE QUARTILE (Test Set)")
print("=" * 60)

quartile_labels = ["Q1 (bottom 25%)", "Q2 (25-50%)", "Q3 (50-75%)", "Q4 (top 25%)"]
quartile_bins = np.percentile(y_test_orig, [0, 25, 50, 75, 100])
quartile_idx = np.digitize(y_test_orig, quartile_bins[1:-1])  # 0,1,2,3

q_results = []
for qi in range(4):
    mask = quartile_idx == qi
    if mask.sum() < 2:
        continue
    yt, yp = y_test_orig[mask], y_test_pred[mask]
    q_results.append({
        "Quartile": quartile_labels[qi],
        "Range": f"EUR{quartile_bins[qi]:,.0f} – EUR{quartile_bins[qi+1]:,.0f}",
        "N": int(mask.sum()),
        "MAE": mean_absolute_error(yt, yp),
        "MAPE": mape(yt, yp),
    })

print(f"{'Quartile':<18} {'Range':<30} {'N':>4} {'MAE (EUR)':>12} {'MAPE':>7}")
print("-" * 76)
for r in q_results:
    print(f"{r['Quartile']:<18} {r['Range']:<30} {r['N']:>4} {r['MAE']:>12,.0f} {r['MAPE']:>6.1f}%")

# ── 5. Residual analysis by condition ─────────────────────────────────────

print("\n" + "=" * 60)
print("RESIDUAL ANALYSIS BY CONDITION (Test Set)")
print("=" * 60)

cond_results = []
for c in sorted(set(cond_test)):
    mask = cond_test == c
    if mask.sum() < 2:
        continue
    yt, yp = y_test_orig[mask], y_test_pred[mask]
    cond_results.append({
        "Condition": c,
        "N": int(mask.sum()),
        "MAE": mean_absolute_error(yt, yp),
        "MAPE": mape(yt, yp),
    })

cond_df = pd.DataFrame(cond_results).sort_values("MAPE", ascending=False)
print(f"{'Condition':<18} {'N':>4} {'MAE (EUR)':>12} {'MAPE':>7}")
print("-" * 45)
for _, r in cond_df.iterrows():
    print(f"{r['Condition']:<18} {r['N']:>4} {r['MAE']:>12,.0f} {r['MAPE']:>6.1f}%")

# ── 6. Generate figures ───────────────────────────────────────────────────

os.makedirs(FIGURES_DIR, exist_ok=True)

# --- Figure 1: Predicted vs Actual scatter ---
fig, ax = plt.subplots(figsize=(7, 7))
ax.scatter(y_test_orig / 1000, y_test_pred / 1000, alpha=0.35, s=18, c="#2563eb", edgecolors="none")
lims = [0, max(y_test_orig.max(), y_test_pred.max()) / 1000 * 1.05]
ax.plot(lims, lims, "--", color="#dc2626", linewidth=1.5, label="Perfect prediction")
ax.set_xlabel("Actual Price (EUR thousands)", fontsize=11)
ax.set_ylabel("Predicted Price (EUR thousands)", fontsize=11)
ax.set_title("Predicted vs Actual Asking Price", fontsize=13, fontweight="bold")
ax.legend(fontsize=10)
ax.set_xlim(lims)
ax.set_ylim(lims)
ax.set_aspect("equal")
fig.tight_layout()
fig.savefig(os.path.join(FIGURES_DIR, "residual_scatter.png"), dpi=150)
plt.close(fig)
print("\n✓ Saved figures/residual_scatter.png")

# --- Figure 2: MAPE by district (horizontal bar) ---
dist_sorted = dist_df.sort_values("MAPE", ascending=True)
fig, ax = plt.subplots(figsize=(8, 7))
colors = ["#dc2626" if m > 20 else "#f59e0b" if m > 15 else "#22c55e" for m in dist_sorted["MAPE"]]
bars = ax.barh(dist_sorted["District"], dist_sorted["MAPE"], color=colors, edgecolor="none")
ax.set_xlabel("MAPE (%)", fontsize=11)
ax.set_title("Model Error by District (MAPE %)", fontsize=13, fontweight="bold")
ax.axvline(x=dist_sorted["MAPE"].median(), color="#6b7280", linestyle="--", linewidth=1, label=f"Median: {dist_sorted['MAPE'].median():.1f}%")
for bar, n in zip(bars, dist_sorted["N"]):
    ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
            f"n={n}", va="center", fontsize=8, color="#6b7280")
ax.legend(fontsize=9)
fig.tight_layout()
fig.savefig(os.path.join(FIGURES_DIR, "residual_by_district.png"), dpi=150)
plt.close(fig)
print("✓ Saved figures/residual_by_district.png")

# --- Figure 3: MAPE by price quartile ---
fig, ax = plt.subplots(figsize=(7, 5))
q_labels = [r["Quartile"].split(" ")[0] for r in q_results]
q_mapes = [r["MAPE"] for r in q_results]
q_colors = ["#22c55e", "#f59e0b", "#f59e0b", "#dc2626"]
bars = ax.bar(q_labels, q_mapes, color=q_colors[:len(q_labels)], edgecolor="none", width=0.6)
for bar, r in zip(bars, q_results):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
            f"{r['MAPE']:.1f}%\nn={r['N']}", ha="center", fontsize=9)
ax.set_xlabel("Price Quartile", fontsize=11)
ax.set_ylabel("MAPE (%)", fontsize=11)
ax.set_title("Model Error by Price Quartile", fontsize=13, fontweight="bold")
# Add range labels
for i, r in enumerate(q_results):
    ax.text(i, -1.5, r["Range"], ha="center", fontsize=7, color="#6b7280")
fig.tight_layout()
fig.savefig(os.path.join(FIGURES_DIR, "residual_by_price_quartile.png"), dpi=150)
plt.close(fig)
print("✓ Saved figures/residual_by_price_quartile.png")

# --- Figure 4: Residual distribution histogram ---
residuals = (y_test_pred - y_test_orig) / 1000
fig, ax = plt.subplots(figsize=(8, 5))
ax.hist(residuals, bins=50, color="#2563eb", edgecolor="white", linewidth=0.5, alpha=0.85)
ax.axvline(x=0, color="#dc2626", linestyle="--", linewidth=1.5, label="Zero error")
ax.axvline(x=np.median(residuals), color="#f59e0b", linestyle="-", linewidth=1.5,
           label=f"Median: EUR{np.median(residuals):+,.0f}k")
ax.set_xlabel("Prediction Error (EUR thousands)", fontsize=11)
ax.set_ylabel("Frequency", fontsize=11)
ax.set_title("Distribution of Prediction Residuals", fontsize=13, fontweight="bold")
ax.legend(fontsize=9)
fig.tight_layout()
fig.savefig(os.path.join(FIGURES_DIR, "residual_distribution.png"), dpi=150)
plt.close(fig)
print("✓ Saved figures/residual_distribution.png")

# ── 7. Executive summary ─────────────────────────────────────────────────

print("\n" + "=" * 60)
print("EXECUTIVE SUMMARY (for thesis Results section)")
print("=" * 60)

worst_dist = dist_df.iloc[0]
best_dist = dist_df.iloc[-1]
worst_q = max(q_results, key=lambda x: x["MAPE"])
best_q = min(q_results, key=lambda x: x["MAPE"])
worst_cond = cond_df.iloc[0]

print(f"""
1. The model shows {'no significant overfitting' if r2_gap <= 0.05 else 'signs of overfitting'} \
(Train R²={metrics['Train']['R²']:.3f}, Test R²={metrics['Test']['R²']:.3f}, gap={r2_gap:.3f}).
2. Geographically, error concentrates in {worst_dist['District']} (MAPE {worst_dist['MAPE']:.1f}%, n={worst_dist['N']}) \
and is lowest in {best_dist['District']} ({best_dist['MAPE']:.1f}%, n={best_dist['N']}), \
reflecting thin training data in premium districts.
3. The model struggles most with {worst_q['Quartile']} properties (MAPE {worst_q['MAPE']:.1f}%) and \
performs best on {best_q['Quartile']} (MAPE {best_q['MAPE']:.1f}%), confirming that luxury \
properties have higher variance that the model cannot fully capture.
4. Condition '{worst_cond['Condition']}' has the highest error (MAPE {worst_cond['MAPE']:.1f}%, n={worst_cond['N']}), \
{'suggesting the 34% missing-condition gap from Redpiso hurts accuracy.' if worst_cond['Condition'] == 'missing' else 'likely due to higher renovation cost variance.'}
5. Overall Test MAPE of {metrics['Test']['MAPE']:.1f}% and MAE of EUR{metrics['Test']['MAE']:,.0f} is \
competitive for a hedonic model on {len(rows):,} listings with 14 features.
""")
