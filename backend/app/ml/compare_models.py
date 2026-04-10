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


MIN_ZONE_FREQUENCY = 10


def _prepare_df(rows, zone_threshold=0):
    """Build DataFrame with optional rare-zone cleanup."""
    df = pd.DataFrame(rows)

    # Map rare zones to empty string to reduce one-hot dimensionality
    if zone_threshold > 0 and "Zona" in df.columns:
        zone_counts = df["Zona"].value_counts()
        rare_zones = set(zone_counts[zone_counts < zone_threshold].index)
        original_zones = df["Zona"].nunique()
        df.loc[df["Zona"].isin(rare_zones), "Zona"] = ""
        kept_zones = df["Zona"].nunique()
        print(f"  Zone cleanup: {original_zones} → {kept_zones} zones (threshold={zone_threshold})")

    for col in ["Distrito", "Zona", "Estado", "Ubicacion"]:
        if col in df.columns:
            df = pd.get_dummies(df, columns=[col], drop_first=False)

    return df


def _run_experiment(df, y, label="", target_is_psqm=False, sizes=None):
    """Train all models on a prepared DataFrame and return results."""
    X_train, X_test, y_train, y_test = train_test_split(
        df, y, test_size=0.15, random_state=42
    )

    # If target is price/sqm, we need the corresponding sizes for train/test sets
    # to convert back to total price for comparable MAE/RMSE
    if target_is_psqm and sizes is not None:
        sizes_train, sizes_test = train_test_split(sizes, test_size=0.15, random_state=42)

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    X_all_s = scaler.transform(df)

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
        print(f"  {label} Training {name}...")
        model.fit(X_train_s, y_train)

        y_pred_log = model.predict(X_test_s)

        if target_is_psqm and sizes is not None:
            # Convert price/sqm predictions back to total price
            y_pred = np.expm1(y_pred_log) * sizes_test
            y_test_orig = np.expm1(y_test) * sizes_test
        else:
            y_pred = np.expm1(y_pred_log)
            y_test_orig = np.expm1(y_test)

        r2 = float(r2_score(y_test_orig, y_pred))
        mae = float(mean_absolute_error(y_test_orig, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_test_orig, y_pred)))
        mape = _mape(np.array(y_test_orig), np.array(y_pred))

        # Train metrics (for overfitting diagnostics)
        y_train_pred_log = model.predict(X_train_s)
        if target_is_psqm and sizes is not None:
            y_train_pred = np.expm1(y_train_pred_log) * sizes_train
            y_train_orig = np.expm1(y_train) * sizes_train
        else:
            y_train_pred = np.expm1(y_train_pred_log)
            y_train_orig = np.expm1(y_train)

        r2_train = float(r2_score(y_train_orig, y_train_pred))
        mae_train = float(mean_absolute_error(y_train_orig, y_train_pred))
        rmse_train = float(np.sqrt(mean_squared_error(y_train_orig, y_train_pred)))
        mape_train = _mape(np.array(y_train_orig), np.array(y_train_pred))

        cv = cross_val_score(model, X_all_s, y, cv=5, scoring="r2")

        results.append({
            "model": name,
            "r2_test": round(r2, 4),
            "mae": round(mae, 0),
            "rmse": round(rmse, 0),
            "mape": round(mape, 2),
            "r2_train": round(r2_train, 4),
            "mae_train": round(mae_train, 0),
            "rmse_train": round(rmse_train, 0),
            "mape_train": round(mape_train, 2),
            "r2_cv_mean": round(float(cv.mean()), 4),
            "r2_cv_std": round(float(cv.std()), 4),
        })
        print(f"    R²={r2:.4f}  MAE={mae:,.0f}  CV={cv.mean():.4f}±{cv.std():.4f}")

    results.sort(key=lambda x: -x["r2_cv_mean"])
    return results


def compare(db_session=None, experiment: str = "a") -> dict:
    rows, targets = build_dataset(db_session)
    if len(rows) < 50:
        return {"error": "Not enough data", "deals": len(rows)}

    y_raw = np.array(targets, dtype=float)
    sizes = np.array([r.get("Metros Cuadrados", 1) or 1 for r in rows], dtype=float)

    # Deep copy rows so mutations don't leak across experiments
    import copy
    exp_rows = copy.deepcopy(rows)

    if experiment == "a":
        # Baseline: zone cleanup, all features
        desc = "Baseline (zone cleanup, all features)"
        df = _prepare_df(exp_rows, zone_threshold=MIN_ZONE_FREQUENCY)
        y = np.log1p(y_raw)

    elif experiment == "b":
        # Drop zone + orientation, keep district + exterior
        desc = "Drop zone + orientation, keep district + exterior"
        for r in exp_rows:
            r["Zona"] = ""
            r["Ubicacion"] = ""
        df = _prepare_df(exp_rows, zone_threshold=0)
        y = np.log1p(y_raw)

    elif experiment == "c":
        # Same as B + impute missing condition as "good"
        desc = "Drop zone + orientation, impute missing condition as good"
        for r in exp_rows:
            r["Zona"] = ""
            r["Ubicacion"] = ""
            if not r.get("Estado") or r["Estado"] == "":
                r["Estado"] = "good"
        df = _prepare_df(exp_rows, zone_threshold=0)
        y = np.log1p(y_raw)

    elif experiment == "c2":
        # Same as B + impute missing condition as "segunda_mano" (treated as good)
        # "segunda mano" is a distinct category — not renew, not new, just used
        desc = "Drop zone + orientation, impute missing condition as segunda_mano"
        for r in exp_rows:
            r["Zona"] = ""
            r["Ubicacion"] = ""
            if not r.get("Estado") or r["Estado"] == "":
                r["Estado"] = "segunda_mano"
        df = _prepare_df(exp_rows, zone_threshold=0)
        y = np.log1p(y_raw)

    elif experiment == "d":
        # Same as B but predict price per sqm
        desc = "Drop zone + orientation, target = price/sqm"
        for r in exp_rows:
            r["Zona"] = ""
            r["Ubicacion"] = ""
        df = _prepare_df(exp_rows, zone_threshold=0)
        y = np.log1p(y_raw / sizes)

    else:
        return {"error": f"Unknown experiment: {experiment}"}

    print(f"=== Experiment {experiment.upper()}: {desc} ===")
    print(f"  Deals: {len(exp_rows)}, Features: {df.shape[1]} columns")

    # For experiment D, we need to convert predictions back to total price for comparable metrics
    results = _run_experiment(df, y, label=f"[{experiment.upper()}]",
                              target_is_psqm=(experiment == "d"),
                              sizes=sizes if experiment == "d" else None)

    return {
        "deals_trained": len(exp_rows),
        "experiment": experiment,
        "description": desc,
        "features": df.shape[1],
        "models": results,
        "best_model": results[0]["model"],
    }
