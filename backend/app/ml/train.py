"""
Retrain the Gradient Boosting valuation model on deals currently in the DB.
Run from the backend/ directory:
    python -m app.ml.train
"""
import logging
import os
import shutil
import sys
from datetime import datetime
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler

# Allow running as a script from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from app.db import models
from app.ml.features import deal_to_features

logger = logging.getLogger(__name__)

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
MIN_PRICE_SQM = 500
MAX_PRICE_SQM = 25000


def build_dataset(db_session=None):
    """
    Build training dataset from all qualifying deals.
    If db_session is provided, use it; otherwise create a new one.
    """
    if db_session is None:
        from app.db.session import SessionLocal
        db = SessionLocal()
        close_db = True
    else:
        db = db_session
        close_db = False

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
        if close_db:
            db.close()

    rows, targets = [], []
    for deal in deals:
        psqm = deal.asking_price / deal.size_sqm
        if psqm < MIN_PRICE_SQM or psqm > MAX_PRICE_SQM:
            continue
        rows.append(deal_to_features(deal))
        targets.append(deal.asking_price)

    logger.info("Training on %d deals (filtered from %d total)", len(rows), len(deals))
    print(f"Training on {len(rows)} deals (filtered from {len(deals)} total)")
    return rows, targets


def train(db_session=None) -> Optional[dict]:
    """
    Train the model and save artifacts. Returns a dict with metrics,
    or None if there is not enough data.

    Parameters
    ----------
    db_session : optional SQLAlchemy session. If None, creates its own.
    """
    rows, targets = build_dataset(db_session)
    if len(rows) < 50:
        logger.warning("Not enough data to train (need at least 50 deals, got %d). Aborting.", len(rows))
        print("Not enough data to train (need at least 50 deals). Aborting.")
        return None

    # Build DataFrame and one-hot encode categoricals
    df = pd.DataFrame(rows)
    for col in ["Distrito", "Zona", "Estado", "Ubicacion"]:
        if col in df.columns:
            df = pd.get_dummies(df, columns=[col], drop_first=False)

    # Log-transform target for better distribution fitting
    y_raw = np.array(targets, dtype=float)
    y = np.log1p(y_raw)

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

    # 5-fold cross-validation on full dataset for stable R² estimate
    X_all_s = scaler.transform(df)
    cv_scores = cross_val_score(model, X_all_s, y, cv=5, scoring="r2")
    cv_mean = float(cv_scores.mean())
    cv_std = float(cv_scores.std())
    logger.info("5-fold CV R²: %.3f (+/- %.3f)", cv_mean, cv_std)
    print(f"5-fold CV R²: {cv_mean:.3f} (+/- {cv_std:.3f})")

    # Evaluate on test set (in original price space)
    y_pred_log = model.predict(X_test_s)
    y_pred = np.expm1(y_pred_log)
    y_test_orig = np.expm1(y_test)

    mae = float(mean_absolute_error(y_test_orig, y_pred))
    r2 = float(r2_score(y_test_orig, y_pred))
    print(f"Test MAE: EUR{mae:,.0f}   R²: {r2:.3f}")

    # Save artifacts with timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    model_version = f"gb_{timestamp}"

    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    timestamped_model = os.path.join(ARTIFACTS_DIR, f"best_gb_model_{timestamp}.pkl")
    timestamped_scaler = os.path.join(ARTIFACTS_DIR, f"scaler_{timestamp}.pkl")
    timestamped_cols = os.path.join(ARTIFACTS_DIR, f"model_columns_{timestamp}.pkl")

    joblib.dump(model, timestamped_model)
    joblib.dump(scaler, timestamped_scaler)
    joblib.dump(list(df.columns), timestamped_cols)

    # Copy as current artifacts (overwrite)
    shutil.copy2(timestamped_model, os.path.join(ARTIFACTS_DIR, "best_gb_model.pkl"))
    shutil.copy2(timestamped_scaler, os.path.join(ARTIFACTS_DIR, "scaler.pkl"))
    shutil.copy2(timestamped_cols, os.path.join(ARTIFACTS_DIR, "model_columns.pkl"))

    logger.info("Artifacts saved to %s (version: %s)", ARTIFACTS_DIR, model_version)
    print(f"Artifacts saved to {ARTIFACTS_DIR} (version: {model_version})")

    return {
        "deals_trained": len(rows),
        "r2_score": r2,
        "r2_cv_mean": cv_mean,
        "r2_cv_std": cv_std,
        "mae": mae,
        "model_version": model_version,
    }


if __name__ == "__main__":
    result = train()
    if result is None:
        sys.exit(1)
