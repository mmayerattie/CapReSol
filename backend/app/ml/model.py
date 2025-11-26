import os
from functools import lru_cache
from typing import Dict, Any
import joblib
import pandas as pd

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")


@lru_cache
def load_model():
    path = os.path.join(ARTIFACTS_DIR, "best_gb_model.pkl")
    return joblib.load(path)


@lru_cache
def load_scaler():
    path = os.path.join(ARTIFACTS_DIR, "scaler.pkl")
    return joblib.load(path)


@lru_cache
def load_columns():
    path = os.path.join(ARTIFACTS_DIR, "model_columns.pkl")
    return joblib.load(path)  # this is a Python list


def predict_price_from_features(features: Dict[str, Any]) -> float:
    """
    features should contain keys like:
      'Numero de Habitaciones', 'Numero de Baños',
      'Metros Cuadrados',
      'Planta', 'Trastero', 'Terraza', 'Balcon',
      'Ascensor', 'Garaje',
      'Distrito', 'Zona', 'Estado', 'Ubicacion'
    """
    # 1) One-row DataFrame
    df = pd.DataFrame([features])

    # 2) One-hot encode the same categorical columns as in training
    for col in ["Distrito", "Zona", "Estado", "Ubicacion"]:
        if col in df.columns:
            df = pd.get_dummies(df, columns=[col], drop_first=False)

    # 3) Align with training columns
    expected_cols = load_columns()
    df = df.reindex(columns=expected_cols, fill_value=0)

    # 4) Scale
    scaler = load_scaler()
    X_scaled = scaler.transform(df)

    # 5) Predict
    model = load_model()
    y_pred = model.predict(X_scaled)

    return float(y_pred[0])