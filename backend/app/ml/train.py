"""
Retrain the Gradient Boosting valuation model on deals currently in the DB.
Run from the backend/ directory:
    python -m app.ml.train
"""
import os
import sys
import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

# Allow running as a script from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from app.db.session import SessionLocal
from app.db import models
from app.ml.features import deal_to_features

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
MIN_PRICE_SQM = 500
MAX_PRICE_SQM = 25000


def build_dataset():
    db = SessionLocal()
    try:
        deals = (
            db.query(models.Deal)
            .filter(
                models.Deal.asking_price.isnot(None),
                models.Deal.size_sqm.isnot(None),
                models.Deal.size_sqm != 0,
            )
            .all()
        )
    finally:
        db.close()

    rows, targets = [], []
    for deal in deals:
        psqm = deal.asking_price / deal.size_sqm
        if psqm < MIN_PRICE_SQM or psqm > MAX_PRICE_SQM:
            continue
        rows.append(deal_to_features(deal))
        targets.append(deal.asking_price)

    print(f"Training on {len(rows)} deals (filtered from {len(deals)} total)")
    return rows, targets


def train():
    rows, targets = build_dataset()
    if len(rows) < 50:
        print("Not enough data to train (need at least 50 deals). Aborting.")
        sys.exit(1)

    # Build DataFrame and one-hot encode categoricals
    df = pd.DataFrame(rows)
    for col in ["Distrito", "Zona", "Estado", "Ubicacion"]:
        if col in df.columns:
            df = pd.get_dummies(df, columns=[col], drop_first=False)

    y = pd.Series(targets)

    X_train, X_test, y_train, y_test = train_test_split(
        df, y, test_size=0.15, random_state=42
    )

    # Scale
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    # Train
    model = GradientBoostingRegressor(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        random_state=42,
    )
    model.fit(X_train_s, y_train)

    # Evaluate
    y_pred = model.predict(X_test_s)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    print(f"Test MAE: €{mae:,.0f}   R²: {r2:.3f}")

    # Save artifacts
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    joblib.dump(model,  os.path.join(ARTIFACTS_DIR, "best_gb_model.pkl"))
    joblib.dump(scaler, os.path.join(ARTIFACTS_DIR, "scaler.pkl"))
    joblib.dump(list(df.columns), os.path.join(ARTIFACTS_DIR, "model_columns.pkl"))
    print(f"Artifacts saved to {ARTIFACTS_DIR}")


if __name__ == "__main__":
    train()
