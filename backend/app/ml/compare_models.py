"""
Compare four regression models on the deals dataset.
Returns metrics for each so the best can be selected for production use.
"""
import logging
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler

from app.ml.train import build_dataset

logger = logging.getLogger(__name__)


def _mape(y_true, y_pred):
    mask = y_true != 0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def compare(db_session=None) -> dict:
    rows, targets = build_dataset(db_session)
    if len(rows) < 50:
        return {"error": "Not enough data", "deals": len(rows)}

    df = pd.DataFrame(rows)
    for col in ["Distrito", "Zona", "Estado", "Ubicacion"]:
        if col in df.columns:
            df = pd.get_dummies(df, columns=[col], drop_first=False)

    y_raw = np.array(targets, dtype=float)
    y = np.log1p(y_raw)

    X_train, X_test, y_train, y_test = train_test_split(
        df, y, test_size=0.15, random_state=42
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    X_all_s = scaler.transform(df)

    # Define models
    models = {
        "Linear Regression": LinearRegression(),
        "Random Forest": RandomForestRegressor(
            n_estimators=300, max_depth=15, random_state=42, n_jobs=-1
        ),
        "Gradient Boosting": GradientBoostingRegressor(
            n_estimators=300, max_depth=5, learning_rate=0.05,
            subsample=0.8, random_state=42
        ),
    }

    # Try importing XGBoost
    try:
        from xgboost import XGBRegressor
        models["XGBoost"] = XGBRegressor(
            n_estimators=300, max_depth=5, learning_rate=0.05,
            subsample=0.8, random_state=42, verbosity=0
        )
    except ImportError:
        logger.warning("XGBoost not installed, skipping")

    results = []
    for name, model in models.items():
        logger.info("Training %s...", name)
        print(f"Training {name}...")
        model.fit(X_train_s, y_train)

        # Test set predictions (reverse log-transform)
        y_pred_log = model.predict(X_test_s)
        y_pred = np.expm1(y_pred_log)
        y_test_orig = np.expm1(y_test)

        r2 = float(r2_score(y_test_orig, y_pred))
        mae = float(mean_absolute_error(y_test_orig, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_test_orig, y_pred)))
        mape = _mape(np.array(y_test_orig), np.array(y_pred))

        # 5-fold CV
        cv = cross_val_score(model, X_all_s, y, cv=5, scoring="r2")

        results.append({
            "model": name,
            "r2_test": round(r2, 4),
            "mae": round(mae, 0),
            "rmse": round(rmse, 0),
            "mape": round(mape, 2),
            "r2_cv_mean": round(float(cv.mean()), 4),
            "r2_cv_std": round(float(cv.std()), 4),
        })
        print(f"  R²={r2:.4f}  MAE={mae:,.0f}  RMSE={rmse:,.0f}  MAPE={mape:.2f}%  CV={cv.mean():.4f}±{cv.std():.4f}")

    results.sort(key=lambda x: -x["r2_cv_mean"])

    return {
        "deals_trained": len(rows),
        "models": results,
        "best_model": results[0]["model"],
    }
