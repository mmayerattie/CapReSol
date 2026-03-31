from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db

router = APIRouter(prefix="/ml", tags=["ml"], dependencies=[Depends(get_current_user)])


class RetrainResult(BaseModel):
    deals_trained: int
    r2_score: float
    r2_cv_mean: float
    r2_cv_std: float
    mae: float
    model_version: str


class ModelMetrics(BaseModel):
    model: str
    r2_test: float
    mae: float
    rmse: float
    mape: float
    r2_cv_mean: float
    r2_cv_std: float


class CompareResult(BaseModel):
    deals_trained: int
    models: List[ModelMetrics]
    best_model: str


@router.post("/compare")
def compare_models(experiment: str = "a", db: Session = Depends(get_db)):
    """Train and compare models. experiment='a' for baseline, 'b' for zone cleanup."""
    from app.ml.compare_models import compare
    result = compare(db_session=db, experiment=experiment)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/retrain", response_model=RetrainResult)
def retrain_model(db: Session = Depends(get_db)):
    """
    Retrain the Gradient Boosting valuation model on all deals in the DB.
    Clears the cached model artifacts so subsequent predictions use the new model.
    """
    from app.ml.train import train
    from app.ml.model import load_model, load_scaler, load_columns

    result = train(db_session=db)

    if result is None:
        raise HTTPException(status_code=400, detail="Not enough data to train (need at least 50 deals)")

    # Clear lru_cache so next prediction loads the fresh artifacts
    load_model.cache_clear()
    load_scaler.cache_clear()
    load_columns.cache_clear()

    return RetrainResult(
        deals_trained=result["deals_trained"],
        r2_score=result["r2_score"],
        r2_cv_mean=result["r2_cv_mean"],
        r2_cv_std=result["r2_cv_std"],
        mae=result["mae"],
        model_version=result["model_version"],
    )
